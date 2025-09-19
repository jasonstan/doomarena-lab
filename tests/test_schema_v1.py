from pathlib import Path
import csv
import json

from tools.apply_schema_v1 import ensure_schema_column, write_run_json, SCHEMA_VERSION


def _write_csv(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_ensure_schema_column_adds_or_overwrites(tmp_path: Path):
    csvp = tmp_path / "summary.csv"
    _write_csv(csvp, [{"exp": "a", "trials": "2", "successes": "1"}])
    ensure_schema_column(csvp)
    rows = list(csv.DictReader(csvp.open()))
    assert "schema" in rows[0]
    assert rows[0]["schema"] == SCHEMA_VERSION

    # overwrite existing different value
    _write_csv(csvp, [{"exp": "a", "schema": "old", "trials": "1", "successes": "1"}])
    ensure_schema_column(csvp)
    rows = list(csv.DictReader(csvp.open()))
    assert rows[0]["schema"] == SCHEMA_VERSION


def test_write_run_json(tmp_path: Path):
    write_run_json(tmp_path)
    data = json.loads((tmp_path / "run.json").read_text())
    assert data["results_schema"] == SCHEMA_VERSION
    assert data["summary_schema"] == SCHEMA_VERSION
    assert isinstance(data["git"], dict)
