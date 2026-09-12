"""reshape stored extractions for the 5.8 schema

Written by hand: `--autogenerate` never sees this. The extraction lives in a JSONB column
with no structure declared to the database, so the shape change that 5.8 makes to
`PliegoExtraction` is invisible to a schema diff -- and yet every row written before it
stops validating the moment the application reads one, because the model is
`extra="forbid"`. Without this, an existing install answers 500 on every
`GET /tenders/{expediente}/analysis` that has a stored extraction.

Two changes, both inside the JSON:

- `certifications` goes from `list[str]` plus one shared `certifications_citation` to a
  list of objects, each with its own `role` and `citation`.
- `execution_deadline` gains `extensions_allowed` and `extensions_description`.

**This migration preserves meaning; it does not improve it.** Every migrated
certification gets `role = "required_to_bid"`, because that is exactly what the old field
declared itself to be ("certifications the provider must already hold"). That is the
faithful conversion, and it deliberately keeps whatever wrong verdicts a pre-5.8
extraction already produced: a data migration that silently re-labelled rows would change
verdicts on evidence nobody re-read. The fix for a contaminated row is to analyze that
tender again -- the new schema is what stops the *next* extraction from making the same
mistake. Same reasoning for `extensions_allowed`, which becomes null: "this extraction
never answered the question", which is true, rather than a guess that reads as an answer.

Revision ID: c3f1ab90d742
Revises: f8bc9ab44cfb
Create Date: 2026-09-12 11:05:18.442310

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1ab90d742"
down_revision: str | Sequence[str] | None = "f8bc9ab44cfb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rewrites every stored extraction into the 5.8 shape.

    Guarded by `jsonb_typeof(... ->'certifications'->0) = 'string'` rather than by row
    count or a flag: it makes the statement idempotent and safe against a database whose
    rows are already mixed, which is what happens if the application wrote a new-shape
    row before this migration ran.
    """
    # certifications: list[str] + one shared citation -> list of objects with their own.
    # The shared citation goes to the first element only: it is a quote, and it names at
    # most the certification it was written for. Handing it to the rest would attach
    # evidence to claims it doesn't mention.
    op.execute(
        """
        UPDATE tender_analyses
        SET extraction = jsonb_set(
            extraction - 'certifications_citation',
            '{certifications}',
            (
                SELECT COALESCE(jsonb_agg(
                    jsonb_build_object(
                        'name', name.value,
                        'role', 'required_to_bid',
                        'citation', CASE
                            WHEN name.ordinality = 1
                            THEN COALESCE(extraction->'certifications_citation', 'null'::jsonb)
                            ELSE 'null'::jsonb
                        END
                    )
                    ORDER BY name.ordinality
                ), '[]'::jsonb)
                FROM jsonb_array_elements_text(extraction->'certifications')
                     WITH ORDINALITY AS name(value, ordinality)
            )
        )
        WHERE extraction IS NOT NULL
          AND jsonb_typeof(extraction->'certifications') = 'array'
          AND (
                jsonb_array_length(extraction->'certifications') = 0
                OR jsonb_typeof(extraction->'certifications'->0) = 'string'
              )
        """
    )

    # execution_deadline: the two new fields, both null -- see the module docstring for
    # why null and not a guess.
    op.execute(
        """
        UPDATE tender_analyses
        SET extraction = jsonb_set(
            extraction,
            '{execution_deadline}',
            (extraction->'execution_deadline')
                || '{"extensions_allowed": null, "extensions_description": null}'::jsonb
        )
        WHERE extraction IS NOT NULL
          AND jsonb_typeof(extraction->'execution_deadline') = 'object'
          AND NOT (extraction->'execution_deadline' ? 'extensions_allowed')
        """
    )


def downgrade() -> None:
    """Flattens the certifications back to names plus one shared citation.

    Lossy on purpose, and in one direction only: the pre-5.8 shape has nowhere to put a
    role, so a certification that was merely scored or was paperwork comes back as a
    requirement -- which is the bug this schema change exists to fix. Downgrading
    reinstates it. The first citation is the one kept, mirroring which one upgrade()
    handed out.
    """
    op.execute(
        """
        UPDATE tender_analyses
        SET extraction = jsonb_set(
            extraction,
            '{certifications}',
            (
                SELECT COALESCE(jsonb_agg(item.value->'name' ORDER BY item.ordinality), '[]'::jsonb)
                FROM jsonb_array_elements(extraction->'certifications')
                     WITH ORDINALITY AS item(value, ordinality)
            )
        ) || jsonb_build_object(
            'certifications_citation',
            COALESCE(extraction->'certifications'->0->'citation', 'null'::jsonb)
        )
        WHERE extraction IS NOT NULL
          AND jsonb_typeof(extraction->'certifications') = 'array'
          AND jsonb_array_length(extraction->'certifications') > 0
          AND jsonb_typeof(extraction->'certifications'->0) = 'object'
        """
    )
    op.execute(
        """
        UPDATE tender_analyses
        SET extraction = extraction || '{"certifications_citation": null}'::jsonb
        WHERE extraction IS NOT NULL
          AND jsonb_typeof(extraction->'certifications') = 'array'
          AND jsonb_array_length(extraction->'certifications') = 0
        """
    )
    op.execute(
        """
        UPDATE tender_analyses
        SET extraction = jsonb_set(
            extraction,
            '{execution_deadline}',
            (extraction->'execution_deadline')
                - 'extensions_allowed' - 'extensions_description'
        )
        WHERE extraction IS NOT NULL
          AND jsonb_typeof(extraction->'execution_deadline') = 'object'
        """
    )
