"""Content reporting and steward review queue handlers."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.forms import ContentReportForm, ContentReportResolveForm
from core.models import ContentReport, Recipe, Review

from ...shared.http import consume_rate_limit
from ...shared.messages import (
    RECIPE_UNAVAILABLE,
    REPORT_ALREADY_OPEN,
    REPORT_ALREADY_REVIEWED,
    REPORT_QUEUE_PERMISSION,
    REPORT_RESOLVE_INVALID,
    REPORT_RESOLVE_RATE_LIMIT,
    REPORT_SELF_REPORT_NOT_ALLOWED,
    REPORT_STATUS_DISMISSED,
    REPORT_STATUS_RESOLVED,
    REPORT_SUBMIT_INVALID,
    REPORT_SUBMIT_RATE_LIMIT,
    REPORT_SUBMIT_SUCCESS,
)
from ...shared.page_content import REPORT_QUEUE_HERO_BADGES
from .helpers import can_review_content_reports, can_view_recipe


def _trim_text(value: str, *, limit: int = 90) -> str:
    """Trim text for compact moderation list previews."""
    text = str(value or '').strip()
    if len(text) <= limit:
        return text
    return f'{text[:limit].rstrip()}...'


def _review_target_summary(review: Review) -> str:
    """Summarize a review for report forms and moderation list previews."""
    return _trim_text(review.content) or f'Note #{review.id}'


def _submit_report(request, *, target_type: str, target_id: int, recipe_id: int):
    """Validate and persist one report submission with de-dup guard."""
    if not consume_rate_limit(request, 'report_submit'):
        messages.error(request, REPORT_SUBMIT_RATE_LIMIT)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    form = ContentReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, REPORT_SUBMIT_INVALID)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    existing_pending = ContentReport.objects.filter(
        reporter=request.user,
        target_type=target_type,
        target_id=target_id,
        status=ContentReport.STATUS_PENDING,
    ).first()
    if existing_pending is not None:
        messages.info(request, REPORT_ALREADY_OPEN)
        return redirect('web-recipe-detail', recipe_id=recipe_id)

    try:
        ContentReport.objects.create(
            reporter=request.user,
            target_type=target_type,
            target_id=target_id,
            reason=form.cleaned_data['reason'],
            details=str(form.cleaned_data.get('details') or '').strip(),
        )
    except IntegrityError:
        # Lost the check-then-create race against the
        # unique_pending_report_per_target constraint: a pending report from
        # this user already exists, so treat it as a duplicate submission.
        messages.info(request, REPORT_ALREADY_OPEN)
        return redirect('web-recipe-detail', recipe_id=recipe_id)
    messages.success(request, REPORT_SUBMIT_SUCCESS)
    return redirect('web-recipe-detail', recipe_id=recipe_id)


def _render_report_form_page(request, *, target_kind: str, target_summary: str, recipe_id: int):
    """Render the standalone report form page for one recipe or note target."""
    return render(
        request,
        'core/pages/moderation/report_form_page.html',
        {
            'report_reason_choices': ContentReport.REASON_CHOICES,
            'report_form': ContentReportForm(),
            'target_kind': target_kind,
            'target_summary': target_summary,
            'recipe_id': recipe_id,
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def report_recipe_page(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    can_view, _ = can_view_recipe(request, recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')
    if recipe.author_id == request.user.id:
        messages.error(request, REPORT_SELF_REPORT_NOT_ALLOWED)
        return redirect('web-recipe-detail', recipe_id=recipe.id)
    if request.method == 'GET':
        return _render_report_form_page(
            request,
            target_kind='recipe',
            target_summary=recipe.title,
            recipe_id=recipe.id,
        )
    return _submit_report(
        request,
        target_type=ContentReport.TARGET_RECIPE,
        target_id=recipe.id,
        recipe_id=recipe.id,
    )


@login_required
@require_http_methods(['GET', 'POST'])
def report_review_page(request, review_id):
    review = get_object_or_404(Review.objects.select_related('recipe'), id=review_id)
    can_view, _ = can_view_recipe(request, review.recipe)
    if not can_view:
        messages.error(request, RECIPE_UNAVAILABLE)
        return redirect('web-home')
    if review.user_id == request.user.id:
        messages.error(request, REPORT_SELF_REPORT_NOT_ALLOWED)
        return redirect('web-recipe-detail', recipe_id=review.recipe_id)
    if request.method == 'GET':
        return _render_report_form_page(
            request,
            target_kind='note',
            target_summary=_review_target_summary(review),
            recipe_id=review.recipe_id,
        )
    return _submit_report(
        request,
        target_type=ContentReport.TARGET_REVIEW,
        target_id=review.id,
        recipe_id=review.recipe_id,
    )


def _attach_report_target_context(reports: list[ContentReport]) -> None:
    """Attach best-effort target preview/url fields for moderation queue rendering."""
    recipe_ids = {report.target_id for report in reports if report.target_type == ContentReport.TARGET_RECIPE}
    review_ids = {report.target_id for report in reports if report.target_type == ContentReport.TARGET_REVIEW}

    recipes = Recipe.objects.in_bulk(recipe_ids)
    reviews = Review.objects.select_related('recipe').in_bulk(review_ids)

    for report in reports:
        report.target_url = ''
        report.target_summary = ''
        report.target_exists = False

        if report.target_type == ContentReport.TARGET_RECIPE:
            recipe = recipes.get(report.target_id)
            if recipe is None:
                continue
            report.target_exists = True
            report.target_summary = _trim_text(recipe.title)
            report.target_url = reverse('web-recipe-detail', args=[recipe.id])
            continue

        review = reviews.get(report.target_id)
        if review is None:
            continue
        report.target_exists = True
        report.target_summary = _review_target_summary(review)
        report.target_url = f"{reverse('web-recipe-detail', args=[review.recipe_id])}#review-{review.id}"


@login_required
@require_GET
def report_queue_page(request):
    if not can_review_content_reports(request.user):
        messages.error(request, REPORT_QUEUE_PERMISSION)
        return redirect('web-home')

    pending_reports = list(
        ContentReport.objects.filter(status=ContentReport.STATUS_PENDING)
        .select_related('reporter')
        .order_by('created_at')
    )
    reviewed_reports = list(
        ContentReport.objects.exclude(status=ContentReport.STATUS_PENDING)
        .select_related('reporter', 'reviewer')
        .order_by('-reviewed_at', '-updated_at')[:40]
    )

    _attach_report_target_context(pending_reports)
    _attach_report_target_context(reviewed_reports)

    return render(
        request,
        'core/pages/moderation/report_queue.html',
        {
            'pending_reports': pending_reports,
            'reviewed_reports': reviewed_reports,
            'resolve_form': ContentReportResolveForm(),
            'hero_badges': REPORT_QUEUE_HERO_BADGES,
        },
    )


@login_required
@require_POST
def resolve_report_page(request, report_id):
    if not can_review_content_reports(request.user):
        messages.error(request, REPORT_QUEUE_PERMISSION)
        return redirect('web-home')

    if not consume_rate_limit(request, 'report_resolve'):
        messages.error(request, REPORT_RESOLVE_RATE_LIMIT)
        return redirect('web-report-queue')

    report = get_object_or_404(ContentReport, id=report_id)
    form = ContentReportResolveForm(request.POST)
    if not form.is_valid():
        messages.error(request, REPORT_RESOLVE_INVALID)
        return redirect('web-report-queue')

    next_status = form.cleaned_data['action']
    now = timezone.now()
    # Update conditionally on the pending status so a concurrent steward
    # decision is never overwritten by a stale read.
    updated_rows = ContentReport.objects.filter(
        id=report.id,
        status=ContentReport.STATUS_PENDING,
    ).update(
        status=next_status,
        reviewer=request.user,
        reviewed_at=now,
        resolution_note=str(form.cleaned_data.get('resolution_note') or '').strip(),
        updated_at=now,
    )
    if updated_rows == 0:
        messages.info(request, REPORT_ALREADY_REVIEWED)
        return redirect('web-report-queue')

    if next_status == ContentReport.STATUS_RESOLVED:
        messages.success(request, REPORT_STATUS_RESOLVED)
    else:
        messages.success(request, REPORT_STATUS_DISMISSED)
    return redirect('web-report-queue')
