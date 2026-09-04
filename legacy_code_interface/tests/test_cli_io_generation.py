from pathlib import Path

from src.cli.cli import CLIGenerator
from src.core.models import Circuit, Template


def test_cli_generator_builds_io_items_from_circuit_templates(tmp_path):
    project_path = tmp_path / "sample.aepj"
    project_path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    generator = CLIGenerator(str(project_path), str(output_dir))

    circuit = Circuit(
        name="C1",
        circuit_number="C1",
        description="Test circuit",
        templates=[Template(name="T1")],
        circuit_ios=[
            {
                "name": "DI_1",
                "description": "Local input",
                "direction": "Input",
                "signal_type": "Digital",
                "io_type": "Status",
            }
        ],
    )
    generator.circuits = [circuit]

    def fake_get_template_ios(template_name: str):
        if template_name == "T1":
            return [
                {
                    "name": "DO_1",
                    "description": "Template output",
                    "direction": "Output",
                    "signal_type": "Digital",
                    "io_type": "Status",
                }
            ]
        return []

    generator.template_mgr.get_template_ios = fake_get_template_ios

    io_items = generator._build_generation_io_items(["C1"], [])

    assert len(io_items) == 2
    assert {item.tag for item in io_items} == {"DI_1", "DO_1"}
    assert any(item.io_type == "Input" for item in io_items)
    assert any(item.io_type == "Output" for item in io_items)
