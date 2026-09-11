"""POST /ingestion/backfill — fill an empty corpus from PLACSP's monthly archives.

Exists for one moment in a Compass install's life: the first one. A fresh database has no
tenders at all, so the funnel has nothing to rank and the dashboard has nothing to show,
and the only way to fix that was a command in the README. This turns it into something the
onboarding screen can trigger.

Not an endpoint for keeping the corpus current -- `daily_ingestion` does that on its own
schedule. This is the cold start.
"""

from fastapi import APIRouter

from compass.ingestion.tasks import backfill_historical_task

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/backfill", status_code=202)
def trigger_backfill() -> dict[str, str]:
    """Enqueues the initial load of the last three months.

    Answers immediately: the work takes minutes (three ~200 MB archives, parsed entry by
    entry) and there is no result backend, so the caller watches the corpus grow through
    `funnel.total` on `GET /matches` instead of waiting on this call. A second request
    while one is running is dropped by the task's own Redis lock, not rejected here --
    same split as `POST /tenders/{expediente}/analyze`.

    Returns:
        A plain acknowledgement.
    """
    backfill_historical_task.delay()
    return {"detail": "Historical backfill queued"}
