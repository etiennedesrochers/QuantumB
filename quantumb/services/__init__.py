"""Service layer: plain-Python facade over the frozen `src.core` engine.

No web framework or GUI imports live here; everything returns plain
dicts/dataclasses so both the FastAPI layer and scripts can use it.
"""

from . import (
    compressor_service,
    generation_service,
    io_service,
    library_service,
    order_service,
    template_service,
    workbook_service,
)
from .errors import (
    GenerationError,
    NotFoundError,
    ServiceError,
    ValidationError,
)

__all__ = [
    "compressor_service",
    "generation_service",
    "io_service",
    "library_service",
    "order_service",
    "template_service",
    "workbook_service",
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "GenerationError",
]
