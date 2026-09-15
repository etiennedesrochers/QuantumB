from quantumb.services.ladder_service import LadderGenerator


def test_ladder_template_selection_uses_secondary_after_first_page(monkeypatch):
    monkeypatch.setattr(
        "quantumb.services.ladder_service.library_service.list_ladder_types",
        lambda: [
            {
                "name": "24VDC",
                "template": "LADDER_WITH_TRANSFORMER",
                "secondary_template": "LADDER_WITHOUT_TRANSFORMER",
            }
        ],
    )

    generator = LadderGenerator([])

    assert generator._template_name("24VDC", 1) == "LADDER_WITH_TRANSFORMER"
    assert generator._template_name("24VDC", 2) == "LADDER_WITHOUT_TRANSFORMER"


def test_string_ladder_types_keep_name_based_template_fallback(monkeypatch):
    monkeypatch.setattr(
        "quantumb.services.ladder_service.library_service.list_ladder_types",
        lambda: ["24VDC"],
    )

    generator = LadderGenerator([])

    assert generator._template_name("24VDC", 1) == "24VDC"
    assert generator._template_name("24VDC", 2) == "24VDC"