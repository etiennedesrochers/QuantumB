"""Typed service errors. The API layer maps these to HTTP status codes."""

from __future__ import annotations


class ServiceError(Exception):
    """Base error for the service layer (maps to HTTP 500)."""


class NotFoundError(ServiceError):
    """Requested resource does not exist (maps to HTTP 404)."""


class ValidationError(ServiceError):
    """Caller supplied an invalid payload (maps to HTTP 400)."""


class GenerationError(ServiceError):
    """Drawing generation failed (maps to HTTP 500)."""
