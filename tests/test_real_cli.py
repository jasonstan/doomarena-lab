import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_MODULE = "scripts.experiments.tau_risky_real"
AGGREGATE_MODULE = "scripts.aggregate_results"
MK_REPORT_PATH = REPO_ROOT / "tools" / "mk_report.py"


def _build_env(workdir: Path, *, overrides: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    paths: list[str] = [str(workdir), str(REPO_ROOT)]
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
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
        "    raise AssertionError('requests.post should not run during dry-run tests')\n",
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


def _run_script(script: Path, args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def _read_run_id(workdir: Path) -> str:
    marker = workdir / "results" / ".run_id"
    assert marker.exists(), "expected results/.run_id marker"
    run_id = marker.read_text(encoding="utf-8").strip()
    assert run_id, ".run_id marker should not be empty"
    return run_id


def _load_run_json(workdir: Path, run_id: str) -> dict[str, object]:
    run_json_path = workdir / "results" / run_id / "tau_risky_real" / "run.json"
    assert run_json_path.exists(), "run.json missing"
    return json.loads(run_json_path.read_text(encoding="utf-8"))


def _load_rows(rows_path: Path) -> list[dict[str, object]]:
    assert rows_path.exists(), f"rows file missing at {rows_path}"
    lines = [line for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "rows.jsonl should not be empty"
    return [json.loads(line) for line in lines]


def test_cli_accepts_legacy_flags(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    env = _build_env(run_in_tmp)
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
        env=env,
    )
    assert "note: --risk is ignored" in result.stdout


def test_cli_prefers_seed_over_seeds(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    env = _build_env(run_in_tmp)
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
        env=env,
    )
    assert "note: both seeds provided; using --seed." in result.stdout
    run_id = _read_run_id(run_in_tmp)
    run_meta = _load_run_json(run_in_tmp, run_id)
    assert run_meta.get("seed") == 314


def test_dry_run_emits_artifacts_and_can_be_aggregated(run_in_tmp: Path) -> None:
    _ensure_requests_stub(run_in_tmp)
    env = _build_env(run_in_tmp)
    _run_module(
        CLI_MODULE,
        ["--dry-run", "--seed", "1", "--trials", "5"],
        cwd=run_in_tmp,
        env=env,
    )

    run_id = _read_run_id(run_in_tmp)
    run_root = run_in_tmp / "results" / run_id
    exp_dir = run_root / "tau_risky_real"
    assert exp_dir.is_dir(), "expected tau_risky_real directory"

    rows_path = exp_dir / "rows.jsonl"
    rows = _load_rows(rows_path)
    assert len(rows) == 5
    allowed_fail_reasons = {"DRY_RUN", "PROVIDER_CALL_BLOCKED_BY_POLICY"}
    observed = {row.get("fail_reason") for row in rows}
    assert observed <= allowed_fail_reasons
    assert "DRY_RUN" in observed

    run_meta = _load_run_json(run_in_tmp, run_id)
    usage = run_meta.get("usage", {}) if isinstance(run_meta, dict) else {}
    assert usage.get("calls_made", 0) == 0
    assert usage.get("tokens_total_sum", 0) == 0

    aggregate_env = _build_env(run_in_tmp)
    _run_module(
        AGGREGATE_MODULE,
        ["--outdir", str(run_root)],
        cwd=run_in_tmp,
        env=aggregate_env,
    )

    summary_path = run_root / "summary.csv"
    assert summary_path.exists(), "summary.csv should be generated"
    summary_text = summary_path.read_text(encoding="utf-8").strip()
    assert "tau_risky_real" in summary_text

    report_env = _build_env(run_in_tmp)
    _run_script(MK_REPORT_PATH, [str(run_root)], cwd=run_in_tmp, env=report_env)
    index_path = run_root / "index.html"
    assert index_path.exists(), "index.html should be produced"
    assert index_path.read_text(encoding="utf-8").lstrip().lower().startswith("<!doctype html>")
