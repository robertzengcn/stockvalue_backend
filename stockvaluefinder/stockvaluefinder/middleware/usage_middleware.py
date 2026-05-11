"""HTTP middleware for tracking API usage per authenticated user.

Intercepts responses after route handlers complete. When
request.state.user_id is present (set by the track_usage dependency),
records the request via UsageTracker. Only tracks paths under /api/v1/
to avoid noise from health checks, docs, and auth endpoints.
"""

import logging

from starlette.requests import Request
from starlette.responses import Response

from stockvaluefinder.middleware.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

# Module-level tracker reference, set by set_usage_tracker during lifespan
_usage_tracker: UsageTracker | None = None


def set_usage_tracker(tracker: UsageTracker) -> None:
    """Set the module-level UsageTracker reference.

    Called during application lifespan after Redis connects and the
    UsageTracker is created by init_usage_tracker in dependencies.py.

    Args:
        tracker: Initialized UsageTracker instance
    """
    global _usage_tracker
    _usage_tracker = tracker


async def usage_tracking_middleware(request: Request, call_next) -> Response:
    """HTTP middleware that records API usage after response.

    Only tracks requests that:
    1. Are under /api/v1/ paths (skip health, docs, auth, root)
    2. Have request.state.user_id set (authenticated via track_usage dependency)

    Args:
        request: Incoming HTTP request
        call_next: Next middleware or route handler callable

    Returns:
        Response from the route handler
    """
    response = await call_next(request)

    # Only track /api/v1/ paths (skip health, docs, auth, root)
    if not request.url.path.startswith("/api/v1/"):
        return response

    # Only track authenticated requests
    if not hasattr(request.state, "user_id"):
        return response

    if _usage_tracker is None:
        return response

    user_id = request.state.user_id
    endpoint = request.url.path
    status_code = response.status_code

    try:
        await _usage_tracker.record_request(
            user_id=user_id,
            endpoint=endpoint,
            status_code=status_code,
        )
    except Exception as e:
        logger.warning(
            f"Usage tracking failed for user {user_id} endpoint {endpoint}: {e}"
        )

    return response
