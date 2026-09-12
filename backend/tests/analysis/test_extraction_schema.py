"""Tests for PliegoExtraction's generated JSON Schema -- what OpenRouter's `strict: true`
structured-output mode actually requires, not assumed from Pydantic's defaults.
"""

from typing import Any

from compass.analysis.extraction_schema import PliegoExtraction


def _object_defs() -> dict[str, Any]:
    """The `$defs` entries that are objects, which are the ones strict mode constrains.

    Since 5.8 `$defs` also holds a plain string enum (`CertificationRole`), which has
    neither `properties` nor `additionalProperties` -- filtering by type keeps these
    tests about what they were always about instead of tripping over a def that has no
    properties to require.
    """
    schema = PliegoExtraction.model_json_schema()
    return {
        name: definition
        for name, definition in schema["$defs"].items()
        if definition.get("type") == "object"
    }


def test_every_object_in_the_schema_forbids_additional_properties() -> None:
    """Protects OpenRouter/OpenAI strict-mode compatibility: every object (top-level and
    nested, via $defs) must set `additionalProperties: false`, or a `strict: true` call
    is rejected outright.
    """
    schema = PliegoExtraction.model_json_schema()

    assert schema["additionalProperties"] is False
    for name, definition in _object_defs().items():
        assert definition["additionalProperties"] is False, name


def test_every_object_in_the_schema_requires_every_property() -> None:
    """Protects the other strict-mode requirement: every declared property must be
    listed as required, even the nullable ones (nullability is expressed via the
    field's type, not by omitting it from `required`).
    """
    schema = PliegoExtraction.model_json_schema()

    assert set(schema["required"]) == set(schema["properties"])
    for name, definition in _object_defs().items():
        assert set(definition["required"]) == set(definition["properties"]), name


def test_the_certification_role_reaches_the_schema_as_a_closed_enum() -> None:
    """Protects the 5.8 fix at the only boundary that can undo it: the model can only
    pick a role if the schema offers the choices. A free-text role would put the
    `required_to_bid` decision back in the model's prose, which is where it went wrong.
    """
    role = PliegoExtraction.model_json_schema()["$defs"]["CertificationRole"]

    assert role["type"] == "string"
    assert set(role["enum"]) == {
        "required_to_bid",
        "award_criterion",
        "administrative_paperwork",
    }
