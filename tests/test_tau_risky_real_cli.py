import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_MODULE = "scripts.experiments.tau_risky_real"
AGGREGATE_MODULE = "scripts.aggregate_results"
RUN_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")


def _base_env(*, prepend: list[Path] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    paths: list[str] = []
    if prepend:
        paths.extend(str(path) for path in prepend)
    paths.append(str(REPO_ROOT))
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _cli_env(workdir: Path, overrides: dict[str, str] | None = None) -> dict[str, str]:
    env = _base_env(prepend=[workdir])
    env.setdefault("GROQ_API_KEY", "test-key")
    if overrides:
        env.update(overrides)
    return env


def _ensure_requests_stub(workdir: Path) -> None:
    stub_path = workdir / "requests.py"
    if stub_path.exists():
        return
    stub_path.write_text(
        "def post(*args, **kwargs):\n"
        "    raise AssertionError('requests.post stub should not be called during dry-run tests')\n",
        encoding="utf-8",
    )


def _run_module(module: str, args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def _run_script(script_path: Path, args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def _read_run_id(workdir: Path) -> str:
    marker = workdir / "results" / ".run_id"
    assert marker.exists(), ".run_id marker missing"
    run_id = marker.read_text(encoding="utf-8").strip()
    assert run_id, "run_id marker is empty"
    assert RUN_PATTERN.match(run_id), f"run_id not ISO-ish: {run_id!r}"
    return run_id


def _load_run_json(workdir: Path, run_id: str) -> dict[str, object]:
    run_json_path = workdir / "results" / run_id / "tau_risky_real" / "run.json"
    assert run_json_path.exists(), "run.json missing"
    return json.loads(run_json_path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict[str, object]]:
    assert path.exists(), f"rows file missing at {path}"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "rows.jsonl is empty"
    return [json.loads(line) for line in lines]


def test_cli_accepts_legacy_flags(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    result = _run_module(
        CLI_MODULE,
        [
            "--seeds",
            "7",
            "--outdir",
            "results",
            "--risk",
            "refund",
            "--dry-run",
            "--trials",
            "1",
        ],
        cwd=run_in_tmp,
        env=_cli_env(run_in_tmp),
    )
    assert result.returncode == 0


def test_cli_prefers_seed_over_seeds(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    result = _run_module(
        CLI_MODULE,
        [
            "--seed",
            "314",
            "--seeds",
            "7",
            "--dry-run",
            "--trials",
            "1",
        ],
        cwd=run_in_tmp,
        env=_cli_env(run_in_tmp),
    )
    assert "note: both seeds provided; using --seed." in result.stdout
    run_id = _read_run_id(run_in_tmp)
    run_meta = _load_run_json(run_in_tmp, run_id)
    assert run_meta.get("seed") == 314


def test_cli_dry_run_writes_marker_and_artifacts(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    _run_module(
        CLI_MODULE,
        ["--dry-run", "--trials", "1", "--seed", "1"],
        cwd=run_in_tmp,
        env=_cli_env(run_in_tmp),
    )
    run_id = _read_run_id(run_in_tmp)
    run_root = run_in_tmp / "results" / run_id
    exp_dir = run_root / "tau_risky_real"
    assert exp_dir.is_dir(), "experiment directory missing"

    rows_path = exp_dir / "rows.jsonl"
    rows = _load_rows(rows_path)
    assert all(row.get("fail_reason") == "DRY_RUN" for row in rows)

    run_meta = _load_run_json(run_in_tmp, run_id)
    usage = run_meta.get("usage", {}) if isinstance(run_meta, dict) else {}
    assert usage.get("calls_made") == 0
    assert usage.get("tokens_total_sum") == 0

    aggregate_env = _base_env()
    _run_module(
        AGGREGATE_MODULE,
        ["--outdir", str(run_root)],
        cwd=run_in_tmp,
        env=aggregate_env,
    )

    summary_csv = run_root / "summary.csv"
    assert summary_csv.exists(), "summary.csv not produced"
    summary_text = summary_csv.read_text(encoding="utf-8").strip()
    assert summary_text, "summary.csv is empty"

    mk_report_env = _base_env()
    _run_script(REPO_ROOT / "tools" / "mk_report.py", [str(run_root)], cwd=run_in_tmp, env=mk_report_env)
    index_html = run_root / "index.html"
    assert index_html.exists(), "index.html not generated"
    html_text = index_html.read_text(encoding="utf-8").strip()
    assert html_text.lower().startswith("<!doctype html>")
