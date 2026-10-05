import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv")
engine = create_engine(DSN, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

STATUS_LABELS = {"pending": "待认领", "done": "已完成", "rejected": "退回"}


class Base(DeclarativeBase):
    pass


class Pairing(Base):
    """双路专页登记表：某断面拱顶左右两支测缝计的编号配对与差值门槛。"""

    __tablename__ = "pairings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    left_gauge: Mapped[str] = mapped_column(String, nullable=False)
    right_gauge: Mapped[str] = mapped_column(String, nullable=False)
    threshold_mm: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConvergenceLog(Base):
    __tablename__ = "convergence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[str] = mapped_column(String, nullable=False)
    left_mm: Mapped[float] = mapped_column(Float, nullable=False)
    right_mm: Mapped[float] = mapped_column(Float, nullable=False)
    diff_mm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    pairing_id: Mapped[int | None] = mapped_column(ForeignKey("pairings.id"), nullable=True)
    # 随单冻结：提交那一刻的配对快照，登记表事后改了旧单配对仍冻结
    pair_left_gauge: Mapped[str | None] = mapped_column(String, nullable=True)
    pair_right_gauge: Mapped[str | None] = mapped_column(String, nullable=True)
    pair_threshold_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def pairing_dict(p: Pairing) -> dict:
    return {
        "id": p.id,
        "section": p.section,
        "left_gauge": p.left_gauge,
        "right_gauge": p.right_gauge,
        "threshold_mm": p.threshold_mm,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "section": row.section,
        "left_mm": row.left_mm,
        "right_mm": row.right_mm,
        "diff_mm": row.diff_mm,
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "verdict": row.verdict,
        "reason": row.reason,
        "pairing_id": row.pairing_id,
        "pair_left_gauge": row.pair_left_gauge,
        "pair_right_gauge": row.pair_right_gauge,
        "pair_threshold_mm": row.pair_threshold_mm,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }
