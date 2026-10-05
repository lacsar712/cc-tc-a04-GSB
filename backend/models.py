import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv")
engine = create_engine(DSN, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class ConvergenceLog(Base):
    __tablename__ = "convergence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chainage: Mapped[str] = mapped_column(String, nullable=False)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "chainage": row.chainage,
        "delta_mm": row.delta_mm,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


class Pairing(Base):
    """拱顶左右两支测缝计的配对登记。一个断面至多一条（唯一约束保证两人同抢至多成功一笔）。"""

    __tablename__ = "dual_pairings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    left_no: Mapped[str] = mapped_column(String, nullable=False)
    right_no: Mapped[str] = mapped_column(String, nullable=False)
    threshold_mm: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DualReport(Base):
    """双路上报：左右两路一次交。配对随单冻结（left_no/right_no/threshold_mm 为快照）。"""

    __tablename__ = "dual_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section: Mapped[str] = mapped_column(String, nullable=False)
    left_mm: Mapped[float] = mapped_column(Float, nullable=False)
    right_mm: Mapped[float] = mapped_column(Float, nullable=False)
    diff_mm: Mapped[float] = mapped_column(Float, nullable=False)
    pairing_id: Mapped[int] = mapped_column(
        ForeignKey("dual_pairings.id"), nullable=False
    )
    left_no: Mapped[str] = mapped_column(String, nullable=False)
    right_no: Mapped[str] = mapped_column(String, nullable=False)
    threshold_mm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def pairing_dict(row: Pairing) -> dict:
    return {
        "id": row.id,
        "section": row.section,
        "left_no": row.left_no,
        "right_no": row.right_no,
        "threshold_mm": row.threshold_mm,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def dual_dict(row: DualReport) -> dict:
    return {
        "id": row.id,
        "section": row.section,
        "left_mm": row.left_mm,
        "right_mm": row.right_mm,
        "diff_mm": row.diff_mm,
        "pairing_id": row.pairing_id,
        "left_no": row.left_no,
        "right_no": row.right_no,
        "threshold_mm": row.threshold_mm,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }
