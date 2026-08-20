"""Recipe creation handlers."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired
from django.shortcuts import redirect, render

from core.forms import RecipeCreateForm
from core.models import Recipe

from ...shared.ai import load_ai_draft_payload
from ...shared.http import consume_rate_limit
from ...shared.idempotency import (
    acquire_inflight_lock,
    canonical_payload_digest,
    clear_idempotency_key,
    idempotency_ttl_seconds,
    read_idempotency_value,
)
from ...shared.messages import (
    RECIPE_CREATE_DUPLICATE_IN_PROGRESS,
    RECIPE_CREATE_DUPLICATE_REDIRECT,
    RECIPE_CREATE_INGREDIENTS_REQUIRED,
    RECIPE_CREATE_RATE_LIMIT,
    RECIPE_CREATE_STEPS_REQUIRED,
    RECIPE_CREATE_SUCCESS_MANUAL,
)
from ...shared.page_content import RECIPE_STUDIO_HERO_BADGES
from ...shared.panels import build_recipe_studio_sidebar_panels
from ...shared.rankings import invalidate_ranking_snapshot_cache
from ...shared.recipe import (
    clear_recipe_create_prefill,
    create_recipe_with_ingredients,
    finalize_recipe_payload,
    parse_ingredients,
    parse_steps,
    read_recipe_create_prefill,
)


def _render_create_recipe_page(request, *, form):
    """Render Create Recipe page with a shared context payload."""
    return render(
        request,
        'core/pages/recipe/create.html',
        {
            'form': form,
            'hero_badges': RECIPE_STUDIO_HERO_BADGES,
            'recipe_studio_sidebar_panels': build_recipe_studio_sidebar_panels(),
        },
    )


def _recipe_create_idempotency_key(*, user_id: int, base_payload: dict) -> str:
    """Build deterministic idempotency key for one create-recipe submission."""
    canonical = {
        'title': str(base_payload.get('title') or '').strip(),
        'description': str(base_payload.get('description') or '').strip(),
        'cuisine': str(base_payload.get('cuisine') or '').strip(),
        'flavor': str(base_payload.get('flavor') or '').strip(),
        'cooking_time': int(base_payload.get('cooking_time') or 0),
        'difficulty': str(base_payload.get('difficulty') or '').strip(),
        'steps': [str(step).strip() for step in (base_payload.get('steps') or []) if str(step).strip()],
        'ingredients': [
            {
                'name': str(row.get('name') or '').strip(),
                'quantity': str(row.get('quantity') or '').strip(),
                'unit': str(row.get('unit') or '').strip(),
                'alternative': str(row.get('alternative') or '').strip(),
            }
            for row in (base_payload.get('ingredients') or [])
        ],
    }
    digest = canonical_payload_digest(canonical)
    return f'recipe:create:idempotency:{user_id}:{digest}'


def _redirect_if_duplicate_submission(request, *, idempotency_key: str):
    """Return redirect response when this create request was already processed or in-flight."""
    existing_value = read_idempotency_value(idempotency_key)
    if isinstance(existing_value, int):
        existing_recipe = Recipe.objects.only('id').filter(id=existing_value).first()
        if existing_recipe:
            messages.info(request, RECIPE_CREATE_DUPLICATE_REDIRECT)
            return redirect('web-recipe-detail', recipe_id=existing_recipe.id)
    messages.info(request, RECIPE_CREATE_DUPLICATE_IN_PROGRESS)
    return redirect('web-recipe-create')


def _resolve_ai_source_metadata(request, *, form) -> tuple[bool, dict]:
    """Resolve hidden AI draft linkage back into source metadata when still available."""
    draft_id = str(form.cleaned_data.get('source_draft_id') or '').strip()
    draft_token = str(form.cleaned_data.get('source_draft_token') or '').strip()
    if not draft_id or not draft_token:
        return False, {}

    try:
        _, source_payload, generated_model = load_ai_draft_payload(
            request,
            draft_token=draft_token,
            draft_id=draft_id,
            consume=False,
        )
    except (BadSignature, SignatureExpired, ValueError):
        return False, {}

    source_data = dict(source_payload)
    if generated_model:
        source_data['model'] = generated_model
    return True, source_data


@login_required
def create_recipe_page(request):
    if request.method == 'POST':
        form = RecipeCreateForm(request.POST)
        if form.is_valid():
            steps = parse_steps(form.cleaned_data['steps_text'])
            ingredient_rows = parse_ingredients(form.cleaned_data['ingredients_text'])
            if not steps:
                form.add_error('steps_text', RECIPE_CREATE_STEPS_REQUIRED)
            if not ingredient_rows:
                form.add_error('ingredients_text', RECIPE_CREATE_INGREDIENTS_REQUIRED)

            if not form.errors:
                if not consume_rate_limit(request, 'recipe_create'):
                    messages.error(request, RECIPE_CREATE_RATE_LIMIT)
                    return _render_create_recipe_page(request, form=form)
                base_payload = {
                    'title': form.cleaned_data['title'],
                    'description': form.cleaned_data['description'],
                    'cuisine': form.cleaned_data['cuisine'],
                    'flavor': form.cleaned_data['flavor'],
                    'steps': steps,
                    'cooking_time': form.cleaned_data['cooking_time'],
                    'difficulty': form.cleaned_data['difficulty'],
                    'ingredients': ingredient_rows,
                    'nutrition': {},
                }
                recipe_payload = finalize_recipe_payload(
                    base_payload,
                    fallback_steps=steps,
                    fallback_ingredients=ingredient_rows,
                )
                idempotency_key = _recipe_create_idempotency_key(
                    user_id=request.user.id,
                    base_payload=base_payload,
                )
                ttl_seconds = idempotency_ttl_seconds('IDEMPOTENCY_RECIPE_CREATE_WINDOW_SECONDS')
                lock_acquired = acquire_inflight_lock(idempotency_key, timeout=ttl_seconds)
                if not lock_acquired:
                    return _redirect_if_duplicate_submission(
                        request,
                        idempotency_key=idempotency_key,
                    )

                is_ai_generated, source_prompt = _resolve_ai_source_metadata(request, form=form)
                try:
                    recipe = create_recipe_with_ingredients(
                        author=request.user,
                        payload=recipe_payload,
                        is_ai_generated=is_ai_generated,
                        source_prompt=source_prompt,
                    )
                except Exception:
                    clear_idempotency_key(idempotency_key)
                    raise

                cache.set(idempotency_key, recipe.id, timeout=ttl_seconds)
                invalidate_ranking_snapshot_cache()
                clear_recipe_create_prefill(request)
                messages.success(request, RECIPE_CREATE_SUCCESS_MANUAL)
                return redirect('web-recipe-detail', recipe_id=recipe.id)
    else:
        if request.GET.get('draft') == '1':
            initial = read_recipe_create_prefill(request)
        else:
            clear_recipe_create_prefill(request)
            initial = {}
        form = RecipeCreateForm(initial=initial)

    return _render_create_recipe_page(request, form=form)
