"""GET /capabilities — what this installation can actually do, given how it's configured.

Exists so the dashboard can tell the reader what is missing *before* they click something
that then fails. Compass is downloaded and run by whoever wants to try it, and the keys it
uses are optional on purpose (5.4, 5.5): without them the ingestion, the funnel, the hybrid
ranking and every screen still work, and only the parts that call an external service are
unavailable.

Deliberately separate from `/health`, whose whole point is that reaching the handler *is*
the check -- mixing configuration state into a liveness probe makes it answer two questions
at once and neither of them clearly.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from compass.core.config import get_settings

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


class CapabilitiesSchema(BaseModel):
    """Which optional pieces are configured.

    Attributes:
        analysis: Whether a pliego can be analyzed at all. `False` means no
            `OPENROUTER_API_KEY`, which is the only thing the analyst agent needs.
        tracing: Whether runs are traced to Langfuse. `False` changes nothing a user
            can see; it's reported so the dashboard can say so rather than leave the
            reader wondering whether something is broken.
    """

    analysis: bool
    tracing: bool


@router.get("")
def read_capabilities() -> CapabilitiesSchema:
    """What this installation is configured to do.

    Returns:
        One boolean per optional capability. No key material, ever -- only whether
        something is set, which is all a browser needs to know.
    """
    settings = get_settings()
    return CapabilitiesSchema(
        analysis=settings.openrouter_api_key is not None,
        tracing=bool(settings.langfuse_public_key and settings.langfuse_secret_key),
    )
