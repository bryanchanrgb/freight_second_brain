from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from freight_second_brain.config import Settings, get_settings
from freight_second_brain.warehouse.schemas import (
    CatalogSource,
    Observation,
    RetrievedSource,
    RunManifest,
    UserFeedback,
)

JSONL_TABLES = {
    "sources": "sources.jsonl",
    "catalog": "catalog.jsonl",
    "feedback": "user_feedback.jsonl",
}

_READ_ONLY_PREFIXES = ("select", "with", "describe", "desc", "show", "explain", "summarize", "from")
_ROW_WRAP_PREFIXES = ("select", "with", "from", "summarize")
_SERIES_COLUMNS = ["source_id", "series_id", "unit", "frequency", "n", "start", "end", "last_value"]
_SQL_TABLES = {
    "sources": RetrievedSource,
    "catalog": CatalogSource,
}


class Warehouse:
    """Local file warehouse plus a read-only DuckDB view for SQL queries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.warehouse_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings.metadata_root.mkdir(parents=True, exist_ok=True)

    @property
    def observations_path(self) -> Path:
        return self.root / "observations.parquet"

    @property
    def observations_csv_path(self) -> Path:
        return self.root / "observations.csv"

    @property
    def duckdb_path(self) -> Path:
        return self.root / "warehouse.duckdb"

    def write_observations(self, rows: Iterable[Observation], *, replace: bool = True) -> int:
        records = [r.model_dump(mode="json") for r in rows]
        if not records:
            frame = pd.DataFrame()
        else:
            frame = pd.DataFrame.from_records(records)
            frame["observed_at"] = pd.to_datetime(frame["observed_at"]).dt.date
        if not replace and self.observations_path.exists() and not frame.empty:
            existing = pd.read_parquet(self.observations_path)
            frame = pd.concat([existing, frame], ignore_index=True)
            frame = frame.drop_duplicates(
                subset=["source_id", "series_id", "observed_at", "vintage_id"],
                keep="last",
            )
        if frame.empty:
            return 0
        frame.to_parquet(self.observations_path, index=False)
        frame.to_csv(self.observations_csv_path, index=False)
        return len(frame)

    def load_observations(self) -> pd.DataFrame:
        if not self.observations_path.exists():
            return pd.DataFrame()
        return pd.read_parquet(self.observations_path)

    def query_observations(
        self,
        *,
        series_id: str | None = None,
        source_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        commodity: str | None = None,
        vessel_class: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        frame = self.load_observations()
        if frame.empty:
            return frame
        if series_id:
            frame = frame[frame["series_id"].astype(str).str.contains(series_id, case=False, na=False)]
        if source_id:
            frame = frame[frame["source_id"] == source_id]
        if commodity:
            frame = frame[frame["commodity"].fillna("").str.contains(commodity, case=False, na=False)]
        if vessel_class:
            frame = frame[frame["vessel_class"].fillna("").str.contains(vessel_class, case=False, na=False)]
        observed = pd.to_datetime(frame["observed_at"])
        if start:
            frame = frame[observed >= pd.Timestamp(start)]
            observed = pd.to_datetime(frame["observed_at"])
        if end:
            frame = frame[observed <= pd.Timestamp(end)]
        return frame.sort_values("observed_at").tail(limit)

    def latest_by_series(self, series_id: str) -> dict[str, Any] | None:
        frame = self.query_observations(series_id=series_id, limit=10_000)
        if frame.empty:
            return None
        row = frame.sort_values("observed_at").iloc[-1]
        return row.to_dict()

    def list_series(self) -> pd.DataFrame:
        frame = self.load_observations()
        if frame.empty:
            return frame
        grouped = (
            frame.groupby(["source_id", "series_id", "unit", "frequency"], dropna=False)
            .agg(
                n=("value", "size"),
                start=("observed_at", "min"),
                end=("observed_at", "max"),
                last_value=("value", "last"),
            )
            .reset_index()
            .sort_values(["source_id", "series_id"])
        )
        return grouped

    def append_jsonl(self, table: str, rows: Iterable[Any]) -> int:
        filename = JSONL_TABLES[table]
        path = self.root / filename
        count = 0
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else row
                handle.write(json.dumps(payload, default=str) + "\n")
                count += 1
        return count

    def replace_jsonl(self, table: str, rows: Iterable[Any]) -> int:
        filename = JSONL_TABLES[table]
        path = self.root / filename
        records = [
            row.model_dump(mode="json") if hasattr(row, "model_dump") else row for row in rows
        ]
        with path.open("w", encoding="utf-8") as handle:
            for payload in records:
                handle.write(json.dumps(payload, default=str) + "\n")
        return len(records)

    def load_jsonl(self, table: str) -> list[dict[str, Any]]:
        path = self.root / JSONL_TABLES[table]
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def write_manifest(self, manifest: RunManifest) -> Path:
        path = self.settings.metadata_root / "latest.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        run_path = self.settings.runs_root / f"{manifest.run_id}.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_manifest(self) -> dict[str, Any] | None:
        path = self.settings.metadata_root / "latest.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_sources(self, rows: Iterable[RetrievedSource]) -> int:
        return self.replace_jsonl("sources", rows)

    def write_feedback(self, row: UserFeedback) -> int:
        return self.append_jsonl("feedback", [row])

    def rebuild_sql(self) -> Path:
        """Materialize a read-only DuckDB database from warehouse files."""
        import duckdb

        path = self.duckdb_path
        path.unlink(missing_ok=True)
        connection = duckdb.connect(str(path))
        try:
            observations = self._observations_frame()
            if observations.empty:
                observations = pd.DataFrame(columns=list(Observation.model_fields.keys()))
            series = self.list_series()
            if series.empty:
                series = pd.DataFrame(columns=_SERIES_COLUMNS)
            self._load_table(connection, "observations", observations)
            self._load_table(connection, "series", series)
            for table, model in _SQL_TABLES.items():
                self._load_jsonl_table(connection, table, model)
        finally:
            connection.close()
        return path

    def sql(self, query: str, *, limit: int = 500) -> dict[str, Any]:
        import duckdb

        sql = query.strip()
        self._assert_read_only(sql)
        if not self.duckdb_path.exists():
            self.rebuild_sql()
        capped = max(1, min(int(limit), 2000))
        wrapped = self._wrap_limit(sql, capped)
        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            frame = connection.execute(wrapped).fetchdf()
        finally:
            connection.close()
        return {
            "sql": sql,
            "columns": list(frame.columns),
            "row_count": len(frame),
            "rows": json.loads(frame.to_json(orient="records", date_format="iso")),
        }

    def schema(self) -> list[dict[str, Any]]:
        import duckdb

        if not self.duckdb_path.exists():
            self.rebuild_sql()
        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            tables = connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
            result: list[dict[str, Any]] = []
            for (table_name,) in tables:
                columns = connection.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'main' AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                    [table_name],
                ).fetchall()
                count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                result.append(
                    {
                        "table": table_name,
                        "row_count": int(count),
                        "columns": [{"name": name, "type": dtype} for name, dtype in columns],
                    }
                )
        finally:
            connection.close()
        return result

    def show_source(self, source_id: str, url: str | None = None, max_chars: int = 4000) -> dict[str, Any]:
        from freight_second_brain.catalog.sources import get_source

        rows = [row for row in self.load_jsonl("sources") if row.get("source_id") == source_id]
        if url:
            rows = [row for row in rows if url in (row.get("canonical_url") or "")]
        catalog = None
        try:
            catalog = get_source(source_id).model_dump(mode="json")
        except KeyError:
            catalog = None
        preview = None
        payload_name = None
        raw_uri = rows[0].get("raw_object_uri") if rows else None
        if raw_uri:
            directory = Path(raw_uri)
            payload = None
            if directory.is_dir():
                skip = {"request.json", "response_headers.json", "manifest.json"}
                files = sorted(path for path in directory.iterdir() if path.is_file() and path.name not in skip)
                payload = files[0] if files else None
            elif directory.is_file():
                payload = directory
            if payload is not None:
                payload_name = payload.name
                preview = payload.read_bytes()[: max_chars * 2].decode("utf-8", errors="replace")[:max_chars]
        return {
            "catalog": catalog,
            "retrieved": rows,
            "raw_object_uri": raw_uri,
            "payload_name": payload_name,
            "preview": preview,
        }

    def _observations_frame(self) -> pd.DataFrame:
        return self._stringify_nested(self.load_observations())

    def _load_table(self, connection: Any, name: str, frame: pd.DataFrame) -> None:
        if frame is None:
            return
        connection.register(f"_tmp_{name}", frame)
        connection.execute(f"CREATE TABLE {name} AS SELECT * FROM _tmp_{name}")
        connection.unregister(f"_tmp_{name}")

    def _load_jsonl_table(self, connection: Any, table: str, model: type | None = None) -> None:
        rows = self.load_jsonl(table)
        if rows:
            frame = self._stringify_nested(pd.DataFrame.from_records(rows))
        elif model is not None:
            frame = pd.DataFrame(columns=list(model.model_fields.keys()))
        else:
            return
        self._load_table(connection, table, frame)

    @staticmethod
    def _stringify_nested(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame.copy()
        for column in out.columns:
            if out[column].dtype != object:
                continue
            out[column] = out[column].map(
                lambda value: json.dumps(value, default=str) if isinstance(value, dict) else value
            )
        return out

    @staticmethod
    def _assert_read_only(sql: str) -> None:
        stripped = sql.strip().rstrip(";").strip()
        if not stripped:
            raise ValueError("SQL query is empty.")
        if ";" in stripped:
            raise ValueError("Only one SQL statement is allowed.")
        first = stripped.split()[0].lower().strip("()")
        if first not in _READ_ONLY_PREFIXES:
            raise ValueError("Only read-only SQL is allowed (SELECT, WITH, DESCRIBE, SHOW, EXPLAIN, SUMMARIZE, FROM).")

    @staticmethod
    def _wrap_limit(sql: str, limit: int) -> str:
        stripped = sql.strip().rstrip(";").strip()
        first = stripped.split()[0].lower().strip("()")
        if first in _ROW_WRAP_PREFIXES:
            return f"SELECT * FROM ({stripped}) AS _q LIMIT {limit}"
        return stripped

