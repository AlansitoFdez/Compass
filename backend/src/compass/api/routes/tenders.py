"""GET /tenders — list tenders with basic filters and pagination."""

from fastapi import APIRouter
from pydantic import BaseModel

from compass.tenders.schemas import TenderSchema

router = APIRouter(prefix="/tenders", tags=["tenders"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class TenderListResponse(BaseModel):
    items: list[TenderSchema]
    total: int
    limit: int
    offset: int
