"""QuantumB rewrite package: service layer + HTTP API over the frozen engine."""

from .legacy_bridge import LEGACY_ROOT, ensure_legacy_importable

ensure_legacy_importable()

__all__ = ["LEGACY_ROOT", "ensure_legacy_importable"]
