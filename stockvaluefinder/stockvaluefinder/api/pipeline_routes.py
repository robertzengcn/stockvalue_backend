"""Pipeline API routes.

Stub router for pipeline endpoints. Health-check endpoint
will be added in Plan 05-03. This file exists so main.py
can include the router without import errors.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/pipeline",
    tags=["pipeline"],
)
