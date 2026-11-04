"""SQLite storage (SQLAlchemy ORM) for users and saved experiment runs (configuration + simulated results).

The traffic dataset itself stays in the CSV file; only run summaries are stored here.
"""
from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, String, create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "traffic_ai.db"
engine = create_engine(f"sqlite:///{DB_PATH}")


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One saved run. `kind` is 'experiment' (one controller of a Fixed-vs-Adaptive comparison) or 'simulation' (a finished live run)."""
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    scenario: Mapped[str] = mapped_column(String(120), default="")
    result: Mapped[dict] = mapped_column(JSON)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def save_run(kind: str, scenario: str, result: dict) -> int:
    with Session(engine) as session:
        run = Run(kind=kind, scenario=scenario, result=result)
        session.add(run)
        session.commit()
        return run.id


def list_runs(kind: str | None = None, limit: int = 20) -> list[dict]:
    query = select(Run).order_by(Run.id.desc()).limit(limit)
    if kind:
        query = query.where(Run.kind == kind)
    with Session(engine) as session:
        return [{"id": r.id, "kind": r.kind, "created_at": r.created_at.isoformat(timespec="seconds"),
                 "scenario": r.scenario, "result": r.result} for r in session.scalars(query)]


def get_run(run_id: int) -> dict | None:
    with Session(engine) as session:
        r = session.get(Run, run_id)
        return None if r is None else {"id": r.id, "kind": r.kind, "created_at": r.created_at.isoformat(timespec="seconds"),
                                       "scenario": r.scenario, "result": r.result}


def clear_runs() -> int:
    with Session(engine) as session:
        deleted = session.execute(delete(Run)).rowcount
        session.commit()
        return deleted


def create_user(username: str, password_hash: str) -> bool:
    """Add a user. Returns False if the username is already taken."""
    with Session(engine) as session:
        session.add(User(username=username, password_hash=password_hash))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return False
        return True


def get_password_hash(username: str) -> str | None:
    with Session(engine) as session:
        return session.scalar(select(User.password_hash).where(User.username == username))
