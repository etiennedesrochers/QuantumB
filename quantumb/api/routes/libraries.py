"""Read and write interfaces for the shared JSON config libraries."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...services import library_service

router = APIRouter(prefix="/api", tags=["libraries"])


@router.get("/circuits")
def list_circuits() -> list[Any]:
    return library_service.list_circuits()


@router.post("/circuits")
def create_circuit(payload: dict[str, Any]) -> dict[str, Any]:
    return library_service.create_circuit(payload)


@router.put("/circuits/{name}")
def update_circuit(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return library_service.update_circuit(name, payload)


@router.delete("/circuits/{name}")
def delete_circuit(name: str) -> dict[str, str]:
    library_service.delete_circuit(name)
    return {"message": f"Circuit '{name}' deleted."}


@router.put("/circuits")
def save_circuits(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return library_service.save_circuits(payload)


@router.get("/modules")
def list_modules() -> list[Any]:
    return library_service.list_modules()


@router.put("/modules")
def save_modules(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return library_service.save_modules(payload)


@router.get("/module-io-values")
def list_module_io_values() -> list[str]:
    return library_service.list_module_io_values()


@router.put("/module-io-values")
def save_module_io_values(payload: list[str]) -> list[str]:
    return library_service.save_module_io_values(payload)


@router.get("/io-types")
def list_io_types() -> list[Any]:
    return library_service.list_io_types()


@router.put("/io-types")
def save_io_types(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return library_service.save_io_types(payload)


@router.get("/ladder-types")
def list_ladder_types() -> list[Any]:
    return library_service.list_ladder_types()


@router.put("/ladder-types")
def save_ladder_types(payload: list[Any]) -> list[Any]:
    return library_service.save_ladder_types(payload)


@router.get("/rules")
def list_rules() -> list[Any]:
    return library_service.list_rules()


@router.put("/rules")
def save_rules(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return library_service.save_rules(payload)


@router.get("/valve-types")
def list_valve_types() -> list[str]:
    return library_service.list_valve_types()


@router.put("/valve-types")
def save_valve_types(payload: list[str]) -> list[str]:
    return library_service.save_valve_types(payload)


@router.get("/valve-ios")
def list_valve_ios() -> dict[str, list[dict[str, Any]]]:
    return library_service.list_valve_ios()


@router.put("/valve-ios")
def save_valve_ios(payload: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return library_service.save_valve_ios(payload)


@router.get("/app-config")
def get_app_config() -> dict[str, Any]:
    return library_service.get_app_config()


@router.put("/app-config")
def save_app_config(payload: dict[str, Any]) -> dict[str, Any]:
    return library_service.save_app_config(payload)
