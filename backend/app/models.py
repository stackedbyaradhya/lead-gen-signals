from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    total_rows: Mapped[int] = mapped_column(Integer)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(255), index=True)
    employees: Mapped[int] = mapped_column(Integer, index=True)
    message_variant: Mapped[str] = mapped_column(String(255), index=True)
    baseline_score: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    outcome_events: Mapped[list] = relationship(
        "OutcomeEvent",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_leads_industry_employees", "industry", "employees"),)


class OutcomeEvent(Base):
    __tablename__ = "outcome_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped[Lead] = relationship(back_populates="outcome_events")
