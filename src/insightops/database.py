"""Local SQLite reference loader; production uses the PostgreSQL schema in /sql."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import pandas as pd


def load_sqlite(path: str | Path, tables: dict[str, pd.DataFrame]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        for name, frame in tables.items():
            serializable = frame.copy()
            for column in serializable.select_dtypes(include="object"):
                serializable[column] = serializable[column].map(
                    lambda value: json.dumps(value, ensure_ascii=False, default=str)
                    if isinstance(value, (dict, list, tuple, set)) else value
                )
            serializable.to_sql(name, connection, if_exists="replace", index=False)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_metric_period ON metric_results(metric_id, period)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_period ON anomaly_results(period, severity)")
    return target


def load_sqlalchemy(database_url: str, tables: dict[str, pd.DataFrame]) -> None:
    """Load curated tables through SQLAlchemy into PostgreSQL or another supported engine."""
    from sqlalchemy import create_engine

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        for name, frame in tables.items():
            frame.to_sql(name, connection, if_exists="append", index=False, method="multi", chunksize=1000)
