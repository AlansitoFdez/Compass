"""Tests for PliegoExtraction's generated JSON Schema -- what OpenRouter's `strict: true`
structured-output mode actually requires, not assumed from Pydantic's defaults.
"""

from compass.analysis.extraction_schema import PliegoExtraction


def test_every_object_in_the_schema_forbids_additional_properties() -> None:
    """Protects OpenRouter/OpenAI strict-mode compatibility: every object (top-level and
    nested, via $defs) must set `additionalProperties: false`, or a `strict: true` call
    is rejected outright.
    """
    schema = PliegoExtraction.model_json_schema()

    assert schema["additionalProperties"] is False
    for name, definition in schema["$defs"].items():
        assert definition["additionalProperties"] is False, name


def test_every_object_in_the_schema_requires_every_property() -> None:
    """Protects the other strict-mode requirement: every declared property must be
    listed as required, even the nullable ones (nullability is expressed via the
    field's type, not by omitting it from `required`).
    """
    schema = PliegoExtraction.model_json_schema()

    assert set(schema["required"]) == set(schema["properties"])
    for name, definition in schema["$defs"].items():
        assert set(definition["required"]) == set(definition["properties"]), name
