"""SQLAlchemy ORM model for public tenders (licitaciones)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from compass.core.db import Base
from compass.tenders.enums import ContractType, TenderStatus


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        # GIN sobre el array: acelera `@>`/`&&`/`=` (el caso de código CPV
        # completo, ver repository.py). No acelera el LIKE sobre elementos
        # desanidados que usa el filtro por prefijo/división -- ese sigue
        # siendo Seq Scan, documentado en phase1.11.md (paso 7).
        Index("ix_tenders_cpv_codes_gin", "cpv_codes", postgresql_using="gin"),
    )

    expediente: Mapped[str] = mapped_column(String, primary_key=True)
    contracting_body: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    cpv_codes: Mapped[list[str]] = mapped_column(ARRAY(String))

    budget_with_vat: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    budget_without_vat: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    contract_type: Mapped[ContractType] = mapped_column(
        SqlEnum(
            ContractType,
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )
    procedure_type: Mapped[str] = mapped_column(String)
    status: Mapped[TenderStatus] = mapped_column(
        SqlEnum(
            TenderStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        )
    )

    submission_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String)

    pcap_url: Mapped[str | None] = mapped_column(String)
    ppt_url: Mapped[str | None] = mapped_column(String)
    platform_url: Mapped[str | None] = mapped_column(String)

    # index=True: GET /tenders siempre ordena por este campo (ver repository.py).
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at_source: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
