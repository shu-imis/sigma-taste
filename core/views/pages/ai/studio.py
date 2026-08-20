"""AI recipe generation and publish handlers."""

import logging
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired
from django.shortcuts import redirect
from django.urls import reverse

from core.forms import AIGenerateForm
from core.services.ai import (
    OllamaError,
    generate_recipe,
    list_available_models,
    resolve_model_name,
    select_session_or_default_model,
    store_session_selected_model,
)
from core.services.recipe import normalize_ai_recipe_payload

from ...shared.ai import issue_ai_draft, load_ai_draft_payload, peek_ai_draft_payload
from ...shared.http import consume_rate_limit
from ...shared.idempotency import (
    acquire_inflight_lock,
    canonical_payload_digest,
    clear_idempotency_key,
    idempotency_ttl_seconds,
    read_idempotency_value,
)
from ...shared.messages import (
    AI_GENERATE_DUPLICATE_IN_PROGRESS,
    AI_GENERATE_DUPLICATE_REUSED,
    AI_GENERATE_RATE_LIMIT,
    AI_GENERATE_UNAVAILABLE,
    AI_MODEL_REQUIRED,
    AI_MODEL_SET_SUCCESS,
    AI_MODEL_UNAVAILABLE,
    AI_PUBLISH_DRAFT_EXPIRED,
    AI_PUBLISH_RATE_LIMIT,
    AI_PUBLISH_SUCCESS,
    RECIPE_CREATE_DRAFT_READY,
)
from ...shared.rankings import invalidate_ranking_snapshot_cache
from ...shared.recipe import (
    build_recipe_create_initial,
    create_recipe_with_ingredients,
    stash_recipe_create_prefill,
)
from .helpers import (
    build_ai_form_from_post_data,
    build_default_ai_form,
    parse_available_ingredient_names,
    render_ai_generate_page,
)

logger = logging.getLogger(__name__)


def _ai_generate_idempotency_key(
    *,
    user_id: int,
    session_key: str,
    selected_model: str,
    payload: dict,
) -> str:
    """Build deterministic cache key for de-duplicating short-interval AI generation requests."""
    canonical = {
        'session_key': str(session_key or ''),
        'model': str(selected_model or '').strip(),
        'available_ingredients': [str(item).strip() for item in (payload.get('available_ingredients') or [])],
        'cooking_time': int(payload.get('cooking_time') or 0),
        'flavor_preference': str(payload.get('flavor_preference') or '').strip(),
        'cuisine_preference': str(payload.get('cuisine_preference') or '').strip(),
        'health_goal': str(payload.get('health_goal') or '').strip(),
        'allergies': str(payload.get('allergies') or '').strip(),
    }
    digest = canonical_payload_digest(canonical)
    return f'ai:generate:idempotency:{user_id}:{digest}'


def _cached_generation_is_reusable(cached_generation: dict) -> bool:
    """Check whether cached generation payload still has a publishable backing draft."""
    publish_draft_id = str(cached_generation.get('publish_draft_id') or '').strip()
    publish_token = str(cached_generation.get('publish_token') or '').strip()
    generated_recipe = cached_generation.get('generated_recipe')
    if not publish_draft_id or not publish_token or not isinstance(generated_recipe, dict):
        return False
    return isinstance(peek_ai_draft_payload(publish_draft_id), dict)


def _normalize_generated_draft(generated_recipe: dict, source_payload: dict) -> dict:
    """Normalize a generated draft exactly once against its source payload before saving."""
    return normalize_ai_recipe_payload(generated_recipe, source_payload)


@login_required
def ai_generate_page(request):
    generated_recipe = None
    generated_model = ''
    publish_token = ''
    publish_draft_id = ''
    available_models = list_available_models()
    default_model = select_session_or_default_model(request, available_models)

    if request.method == 'POST' and request.POST.get('action') == 'publish_generated':
        draft_token = (request.POST.get('draft_token') or '').strip()
        draft_id = (request.POST.get('draft_id') or '').strip()

        if not consume_rate_limit(request, 'ai_publish'):
            messages.error(request, AI_PUBLISH_RATE_LIMIT)
            if draft_token and draft_id:
                try:
                    generated_recipe, _, generated_model = load_ai_draft_payload(
                        request,
                        draft_token=draft_token,
                        draft_id=draft_id,
                        consume=False,
                    )
                except (BadSignature, SignatureExpired, ValueError):
                    generated_recipe = None
                else:
                    publish_token = draft_token
                    publish_draft_id = draft_id
            form = build_default_ai_form(request, default_model, available_models)
            return render_ai_generate_page(
                request,
                form=form,
                generated_recipe=generated_recipe,
                generated_model=generated_model,
                publish_token=publish_token,
                publish_draft_id=publish_draft_id,
                available_models=available_models,
            )

        try:
            generated_recipe, source_payload, generated_model = load_ai_draft_payload(
                request,
                draft_token=draft_token,
                draft_id=draft_id,
                consume=True,
            )
        except (BadSignature, SignatureExpired, ValueError):
            generated_recipe = None
            logger.warning(
                'request_id=%s event=ai_publish_draft_invalid user_id=%s',
                getattr(request, 'request_id', '-'),
                request.user.id,
            )
            messages.error(request, AI_PUBLISH_DRAFT_EXPIRED)
            form = build_default_ai_form(request, default_model, available_models)
        else:
            source_payload['model'] = generated_model
            normalized = _normalize_generated_draft(generated_recipe, source_payload)
            try:
                recipe = create_recipe_with_ingredients(
                    author=request.user,
                    payload=normalized,
                    is_ai_generated=True,
                    source_prompt=source_payload,
                )
            except Exception:
                # The one-time draft was already consumed; re-issue it so the
                # user can retry the publish instead of losing the draft.
                issue_ai_draft(
                    request=request,
                    generated_recipe=generated_recipe,
                    source_payload=source_payload,
                    model=generated_model,
                )
                raise
            invalidate_ranking_snapshot_cache()
            messages.success(request, AI_PUBLISH_SUCCESS)
            return redirect('web-recipe-detail', recipe_id=recipe.id)

    elif request.method == 'POST' and request.POST.get('action') == 'continue_editing':
        draft_token = (request.POST.get('draft_token') or '').strip()
        draft_id = (request.POST.get('draft_id') or '').strip()
        try:
            generated_recipe, source_payload, generated_model = load_ai_draft_payload(
                request,
                draft_token=draft_token,
                draft_id=draft_id,
                consume=False,
            )
        except (BadSignature, SignatureExpired, ValueError):
            messages.error(request, AI_PUBLISH_DRAFT_EXPIRED)
            form = build_default_ai_form(request, default_model, available_models)
        else:
            source_payload['model'] = generated_model
            normalized = _normalize_generated_draft(generated_recipe, source_payload)
            stash_recipe_create_prefill(
                request,
                build_recipe_create_initial(
                    normalized,
                    source_draft_id=draft_id,
                    source_draft_token=draft_token,
                ),
            )
            messages.success(request, RECIPE_CREATE_DRAFT_READY)
            return redirect(f"{reverse('web-recipe-create')}?draft=1")

    elif request.method == 'POST' and request.POST.get('action') == 'set_model':
        form = build_ai_form_from_post_data(
            request.POST,
            fallback_model=default_model,
            available_models=available_models,
        )
        requested_model = str(request.POST.get('model') or '').strip()
        if not requested_model:
            messages.error(request, AI_MODEL_REQUIRED)
            return render_ai_generate_page(
                request,
                form=form,
                generated_recipe=generated_recipe,
                generated_model=generated_model,
                publish_token=publish_token,
                publish_draft_id=publish_draft_id,
                available_models=available_models,
            )

        available_models = list_available_models(refresh=True)
        try:
            selected_model = resolve_model_name(
                requested_model,
                available_models=available_models,
                require_listed=True,
            )
        except OllamaError:
            messages.error(request, AI_MODEL_UNAVAILABLE)
        else:
            messages.success(request, AI_MODEL_SET_SUCCESS)
            store_session_selected_model(request, selected_model)
            form = build_ai_form_from_post_data(
                request.POST,
                fallback_model=selected_model,
                available_models=available_models,
            )

        return render_ai_generate_page(
            request,
            form=form,
            generated_recipe=generated_recipe,
            generated_model=generated_model,
            publish_token=publish_token,
            publish_draft_id=publish_draft_id,
            available_models=available_models,
        )

    elif request.method == 'POST':
        if not consume_rate_limit(request, 'ai_generate'):
            messages.error(request, AI_GENERATE_RATE_LIMIT)
            form = build_default_ai_form(request, default_model, available_models)
            return render_ai_generate_page(
                request,
                form=form,
                generated_recipe=generated_recipe,
                generated_model=generated_model,
                publish_token=publish_token,
                publish_draft_id=publish_draft_id,
                available_models=available_models,
            )

        form = AIGenerateForm(request.POST, available_models=available_models)
        if form.is_valid():
            try:
                selected_model = resolve_model_name(
                    form.cleaned_data.get('model'),
                    available_models=available_models,
                    require_listed=True,
                )
            except OllamaError as exc:
                logger.warning('AI model resolution failed in generation flow: %s', exc)
                messages.error(request, AI_MODEL_UNAVAILABLE)
                selected_model = ''

            payload = {
                'available_ingredients': parse_available_ingredient_names(form.cleaned_data['available_ingredients']),
                'cooking_time': form.cleaned_data['cooking_time'],
                'flavor_preference': form.cleaned_data.get('flavor_preference') or '',
                'cuisine_preference': form.cleaned_data.get('cuisine_preference') or '',
                'health_goal': form.cleaned_data.get('health_goal') or '',
                'allergies': form.cleaned_data.get('allergies') or '',
            }

            if selected_model:
                store_session_selected_model(request, selected_model)
                idempotency_key = _ai_generate_idempotency_key(
                    user_id=request.user.id,
                    session_key=request.session.session_key or '',
                    selected_model=selected_model,
                    payload=payload,
                )
                ttl_seconds = idempotency_ttl_seconds('IDEMPOTENCY_AI_GENERATE_WINDOW_SECONDS')
                lock_acquired = acquire_inflight_lock(idempotency_key, timeout=ttl_seconds)
                if not lock_acquired:
                    cached_generation = read_idempotency_value(idempotency_key)
                    if isinstance(cached_generation, dict) and _cached_generation_is_reusable(cached_generation):
                        generated_recipe = cached_generation['generated_recipe']
                        generated_model = str(cached_generation.get('generated_model') or selected_model)
                        publish_token = str(cached_generation.get('publish_token') or '')
                        publish_draft_id = str(cached_generation.get('publish_draft_id') or '')
                        messages.info(request, AI_GENERATE_DUPLICATE_REUSED)
                    else:
                        messages.info(request, AI_GENERATE_DUPLICATE_IN_PROGRESS)

                if lock_acquired:
                    generate_started_at = time.perf_counter()
                    try:
                        generated_recipe = generate_recipe(payload, model=selected_model, output_language='en')
                        generated_model = selected_model
                        source_payload = dict(payload)
                        source_payload['model'] = selected_model
                        publish_draft_id, publish_token = issue_ai_draft(
                            request=request,
                            generated_recipe=generated_recipe,
                            source_payload=source_payload,
                            model=generated_model,
                        )
                    except OllamaError as exc:
                        clear_idempotency_key(idempotency_key)
                        logger.warning('AI recipe generation failed: %s', exc)
                        messages.error(request, AI_GENERATE_UNAVAILABLE)
                    except Exception:
                        clear_idempotency_key(idempotency_key)
                        raise
                    else:
                        cache.set(
                            idempotency_key,
                            {
                                'generated_recipe': generated_recipe,
                                'generated_model': generated_model,
                                'publish_token': publish_token,
                                'publish_draft_id': publish_draft_id,
                            },
                            timeout=ttl_seconds,
                        )
                    finally:
                        logger.info(
                            'request_id=%s event=ai_generate duration_ms=%.1f',
                            getattr(request, 'request_id', '-'),
                            (time.perf_counter() - generate_started_at) * 1000.0,
                        )
    else:
        form = build_default_ai_form(request, default_model, available_models)

    return render_ai_generate_page(
        request,
        form=form,
        generated_recipe=generated_recipe,
        generated_model=generated_model,
        publish_token=publish_token,
        publish_draft_id=publish_draft_id,
        available_models=available_models,
    )
