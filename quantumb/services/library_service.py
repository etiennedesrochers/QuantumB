"""Read-only access to the shared JSON config libraries."""

from __future__ import annotations

import json
from typing import Any

from ..legacy_bridge import CONFIG_DIR, ensure_legacy_importable
from .errors import ServiceError

ensure_legacy_importable()

import src.core.app_config as app_config  # noqa: E402
import src.core.circuit_library as circuit_library  # noqa: E402
import src.core.module_manager as module_manager  # noqa: E402
import src.core.rules_manager as rules_manager  # noqa: E402
import src.core.valve_manager as valve_manager  # noqa: E402


def _read_config_json(filename: str, default: Any) -> Any:
    path = CONFIG_DIR / filename
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ServiceError(f"Error reading {filename}: {exc}") from exc


def _write_config_json(filename: str, data: Any) -> None:
    path = CONFIG_DIR / filename
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise ServiceError(f"Error writing {filename}: {exc}") from exc


def sort_io_items(ios: list[dict]) -> list[dict]:
    """Sort I/O items by Direction (Input -> Output), Signal Type (Digital -> Analog), and Name."""
    if not isinstance(ios, list):
        return []

    def sort_key(io: dict):
        direction = str(io.get("direction", "")).strip().lower()
        signal_type = str(io.get("signal_type", "")).strip().lower()
        dir_order = 0 if direction == "input" else (1 if direction == "output" else 2)
        sig_order = 0 if signal_type == "digital" else (1 if signal_type == "analog" else 2)
        name = str(io.get("name", "")).strip().lower()
        return (dir_order, sig_order, name)

    return sorted(ios, key=sort_key)


def list_circuits() -> list[dict]:
    return circuit_library.load_library()


def save_circuits(circuits: list[dict]) -> list[dict]:
    for c in circuits:
        if isinstance(c, dict) and "circuit_ios" in c and isinstance(c["circuit_ios"], list):
            c["circuit_ios"] = sort_io_items(c["circuit_ios"])
    ok, msg = circuit_library.save_library(circuits)
    if not ok:
        raise ServiceError(f"Failed to save circuits: {msg}")
    return circuits


def create_circuit(circuit: dict) -> dict:
    circuits = list_circuits()
    name = circuit.get("name")
    if not name:
        raise ServiceError("Circuit name is required.")
    if any(c.get("name") == name for c in circuits):
        raise ServiceError(f"Circuit '{name}' already exists.")
    if "circuit_ios" in circuit and isinstance(circuit["circuit_ios"], list):
        circuit["circuit_ios"] = sort_io_items(circuit["circuit_ios"])
    circuits.append(circuit)
    save_circuits(circuits)
    return circuit


def update_circuit(circuit_name: str, updated_circuit: dict) -> dict:
    circuits = list_circuits()
    found = False
    if "circuit_ios" in updated_circuit and isinstance(updated_circuit["circuit_ios"], list):
        updated_circuit["circuit_ios"] = sort_io_items(updated_circuit["circuit_ios"])
    for i, c in enumerate(circuits):
        if c.get("name") == circuit_name:
            circuits[i] = updated_circuit
            found = True
            break
    if not found:
        raise NotFoundError(f"Circuit '{circuit_name}' not found.")
    save_circuits(circuits)
    return updated_circuit
    save_circuits(circuits)
    return updated_circuit


def delete_circuit(circuit_name: str) -> None:
    circuits = list_circuits()
    new_circuits = [c for c in circuits if c.get("name") != circuit_name]
    if len(new_circuits) == len(circuits):
        raise NotFoundError(f"Circuit '{circuit_name}' not found.")
    save_circuits(new_circuits)


def list_modules() -> list[dict]:
    return module_manager.load_modules()


def save_modules(modules: list[dict]) -> list[dict]:
    ok, msg = module_manager.save_modules(modules)
    if not ok:
        raise ServiceError(f"Failed to save modules: {msg}")
    return modules


def list_module_io_values() -> list[str]:
    return module_manager.load_io_values()


def save_module_io_values(values: list[str]) -> list[str]:
    ok, msg = module_manager.save_io_values(values)
    if not ok:
        raise ServiceError(f"Failed to save module IO values: {msg}")
    return values


def list_rules() -> list[dict]:
    return rules_manager.load_rules()


def save_rules(rules: list[dict]) -> list[dict]:
    ok, msg = rules_manager.save_rules(rules)
    if not ok:
        raise ServiceError(f"Failed to save rules: {msg}")
    return rules


def list_valve_types() -> list[str]:
    return valve_manager.load_valve_types()


def save_valve_types(types: list[str]) -> list[str]:
    valve_manager.save_valve_types(types)
    return types


def list_valve_ios() -> dict[str, list[dict]]:
    return valve_manager.load_valve_ios()


def save_valve_ios(ios: dict[str, list[dict]]) -> dict[str, list[dict]]:
    valve_manager.save_valve_ios(ios)
    return ios


def list_io_types() -> list[dict]:
    """Named I/O types; same file the CLI generator reads."""
    return _read_config_json("io_types_library.json", [])


def save_io_types(io_types: list[dict]) -> list[dict]:
    _write_config_json("io_types_library.json", io_types)
    return io_types


def list_ladder_types() -> list[Any]:
    """`ladder_types.json` stores the list under a `ladder_types` key."""
    data = _read_config_json("ladder_types.json", [])
    if isinstance(data, dict):
        return data.get("ladder_types", [])
    return data


def save_ladder_types(ladder_types: list[Any]) -> list[Any]:
    _write_config_json("ladder_types.json", {"ladder_types": ladder_types})
    return ladder_types


def get_app_config() -> dict:
    return app_config.load_app_config()


def save_app_config(config: dict) -> dict:
    app_config.save_app_config(config)
    return config
