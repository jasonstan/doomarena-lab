import csv
import os
import subprocess
import sys
from pathlib import Path

from tools.check_thresholds import WARN_EXIT_CODE

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPO_ROOT / "tools" / "check_thresholds.py"


def _setup_run(tmp_path: Path) -> tuple[Path, str]:
    results_root = tmp_path / "results"
    run_id = "2024-01-02T03-04-05Z"
    run_dir = results_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (results_root / ".run_id").write_text(f"{run_id}\n", encoding="utf-8")
    summary_path = run_dir / "summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "exp",
                "total_trials",
                "called_trials",
                "callable",
                "success",
                "post_deny",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "exp": "tau_risky_real",
                "total_trials": 5,
                "called_trials": 4,
                "callable": 4,
                "success": 3,
                "post_deny": 1,
            }
        )
    return results_root, run_id


def _write_thresholds(path: Path, *, policy: str, min_total: int, min_callable: int, min_pass_rate: float, max_post_deny: int) -> None:
    content = (
        "version: 1\n"
        f"policy: {policy}\n"
        f"min_total_trials: {min_total}\n"
        f"min_callable_trials: {min_callable}\n"
        f"min_pass_rate: {min_pass_rate}\n"
        f"max_post_deny: {max_post_deny}\n"
    )
    path.write_text(content, encoding="utf-8")


def _run_check_thresholds(
    *,
    results_root: Path,
    run_id: str,
    thresholds_path: Path,
    strict: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(CHECK_SCRIPT),
        "--results-root",
        str(results_root),
        "--run-id",
        run_id,
        "--thresholds",
        str(thresholds_path),
        "--no-report-update",
    ]
    if strict:
        args.append("--strict")
    return subprocess.run(args, text=True, capture_output=True, check=False)


def test_thresholds_permissive_configuration_reports_ok(tmp_path: Path) -> None:
    results_root, run_id = _setup_run(tmp_path)
    thresholds_path = tmp_path / "thresholds_ok.yaml"
    _write_thresholds(
        thresholds_path,
        policy="warn",
        min_total=1,
        min_callable=1,
        min_pass_rate=0.2,
        max_post_deny=5,
    )

    proc = _run_check_thresholds(results_root=results_root, run_id=run_id, thresholds_path=thresholds_path)
    assert proc.returncode == 0
    assert "THRESHOLDS: OK" in proc.stdout


def test_thresholds_warn_and_fail_behaviour(tmp_path: Path) -> None:
    results_root, run_id = _setup_run(tmp_path)
    thresholds_path = tmp_path / "thresholds_strict.yaml"
    _write_thresholds(
        thresholds_path,
        policy="warn",
        min_total=10,
        min_callable=10,
        min_pass_rate=0.9,
        max_post_deny=0,
    )

    warn_proc = _run_check_thresholds(results_root=results_root, run_id=run_id, thresholds_path=thresholds_path)
    assert warn_proc.returncode == WARN_EXIT_CODE
    assert "THRESHOLDS: WARN" in warn_proc.stdout

    fail_proc = _run_check_thresholds(
        results_root=results_root,
        run_id=run_id,
        thresholds_path=thresholds_path,
        strict=True,
    )
    assert fail_proc.returncode != 0
    assert "THRESHOLDS: FAIL" in fail_proc.stdout
