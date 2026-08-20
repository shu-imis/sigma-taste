"""Request-level observability middleware."""

import base64
import logging
import re
import secrets
import time
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


def _build_csp_nonce() -> str:
    """Return a short base64 nonce suitable for CSP headers and HTML attributes."""
    return base64.b64encode(secrets.token_bytes(16)).decode('ascii')


def _inject_style_nonce(policy: str, nonce: str) -> str:
    """Append the request nonce to the style-src directive without weakening CSP."""
    nonce_source = f"'nonce-{nonce}'"
    directives = [directive.strip() for directive in str(policy or '').split(';') if directive.strip()]
    if not directives:
        return f"default-src 'self'; style-src 'self' {nonce_source}"

    updated_directives: list[str] = []
    style_src_found = False

    for directive in directives:
        if directive.startswith('style-src'):
            style_src_found = True
            if nonce_source not in directive.split()[1:]:
                directive = f'{directive} {nonce_source}'
        updated_directives.append(directive)

    if not style_src_found:
        updated_directives.append(f"style-src 'self' {nonce_source}")

    return '; '.join(updated_directives)


class SecurityHeadersMiddleware:
    """Set strict browser security headers for all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_style_nonce = _build_csp_nonce()
        response = self.get_response(request)
        policy = response.get('Content-Security-Policy') or settings.CONTENT_SECURITY_POLICY
        response['Content-Security-Policy'] = _inject_style_nonce(policy, request.csp_style_nonce)
        response.setdefault('Permissions-Policy', settings.PERMISSIONS_POLICY)
        response.setdefault('Cross-Origin-Opener-Policy', settings.CROSS_ORIGIN_OPENER_POLICY)
        response.setdefault('Cross-Origin-Resource-Policy', settings.CROSS_ORIGIN_RESOURCE_POLICY)
        return response


class RequestTracingMiddleware:
    """Attach request ID and log request latency for every response."""

    REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
    RESPONSE_HEADER = 'X-Request-ID'
    REQUEST_ID_PATTERN = re.compile(r'^[A-Za-z0-9-]{1,64}$')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Reflect only well-formed client request IDs; anything else (including
        # header-smuggling attempts with CR/LF) gets a fresh server-side ID.
        incoming_request_id = (request.META.get(self.REQUEST_ID_HEADER) or '').strip()
        if self.REQUEST_ID_PATTERN.fullmatch(incoming_request_id):
            request_id = incoming_request_id
        else:
            request_id = uuid.uuid4().hex
        request.request_id = request_id
        started_at = time.perf_counter()

        response = self.get_response(request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        response[self.RESPONSE_HEADER] = request_id
        logger.info(
            'request_id=%s method=%s path=%s status=%s duration_ms=%.1f',
            request_id,
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
        )
        return response
