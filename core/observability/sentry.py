"""NFR-5: Sentry error tracking initialization."""

from __future__ import annotations

import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = structlog.get_logger()


def init_sentry(dsn: str, environment: str = "development") -> None:
    """NFR-5: Initialize Sentry SDK with FastAPI + SQLAlchemy integrations.

    Captures unhandled exceptions and tags them with request_id/trace_id
    for correlation with structured logs. Scrubs sensitive headers before
    sending.
    """
    if not dsn:
        logger.info("sentry_disabled", reason="no DSN configured")
        return

    _SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key"}

    def _scrub_request(
        event: dict[str, object], _hint: dict[str, object]
    ) -> dict[str, object] | None:
        """Remove sensitive headers before sending to Sentry."""
        request = event.get("request", {})
        if isinstance(request, dict):
            headers = request.get("headers", {})
            if isinstance(headers, dict):
                request["headers"] = {
                    k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS
                }
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(
                failed_request_status_codes={500, 501, 502, 503, 504},
            ),
            SqlalchemyIntegration(),
        ],
        before_send=_scrub_request,  # type: ignore[arg-type]
        send_default_pii=False,
    )
    logger.info("sentry_initialized", environment=environment)
