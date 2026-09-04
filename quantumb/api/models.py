"""Pydantic schemas for the QuantumB API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TemplateRef(BaseModel):
    """A template attached to a compressor in the shared library."""

    model_config = ConfigDict(extra="ignore")

    id: str | int | None = None
    name: str
    type: str = "regular"
    scope: Literal["shared", "per_unit"] = "per_unit"


class CompressorCreate(BaseModel):
    name: str = Field(min_length=1)
    model: str = ""
    manufacturer: str = ""
    capacity: float = 0
    templates: list[TemplateRef] = Field(default_factory=list)


class CompressorUpdate(BaseModel):
    """All fields optional; only the ones sent are written."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    capacity: float | None = None
    templates: list[TemplateRef] | None = None


class CompressorImport(BaseModel):
    compressors: list[dict[str, Any]]
    mode: Literal["merge", "replace"] = "merge"


class SelectionTemplate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    quantity: int = 1


class SelectionCompressor(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_number: str = ""
    description: str = ""
    templates: list[SelectionTemplate] = Field(default_factory=list)


class SelectionCircuit(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    valves: dict[str, int] = Field(default_factory=dict)
    compressors: list[SelectionCompressor] = Field(default_factory=list)


class SelectionPayload(BaseModel):
    """Body of `POST /api/generate` (same shape the legacy CLI consumes)."""

    model_config = ConfigDict(extra="allow")

    project_name: str = ""
    project_number: str = ""
    revision: str = "A"
    drawn_by: str = ""
    manufacturer: str = ""
    circuits: list[SelectionCircuit] = Field(min_length=1)


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
