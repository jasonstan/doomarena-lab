from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

try:
    from tools.report.html_utils import esc, preview_block
except Exception:  # fallback for older runners
    import html

    def esc(s: object) -> str:
        if s is None:
            return ""
        return html.escape(str(s), quote=True)

    def preview_block(full_text: str, max_len: int = 160) -> str:
        text = full_text or ""
        short = (text[:max_len] + "…") if len(text) > max_len else text
        return (
            f"<details><summary><code>{esc(short)}</code></summary>"
            f"<pre style='white-space:pre-wrap'>{esc(text)}</pre></details>"
        )


def _read_jsonl_lines(p: Path) -> Iterator[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _join_user_messages(messages: Any) -> Optional[str]:
    if not isinstance(messages, list):
        return None
    parts = []
    for m in messages:
        if isinstance(m, dict) and m.get("role") in ("user", "system"):
            content = m.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        parts.append(str(b.get("text", "")))
    return "\n".join(p for p in parts if p) or None


def _openai_like(raw: Any) -> Optional[str]:
    try:
        return raw["choices"][0]["message"]["content"]
    except Exception:
        try:
            return raw["choices"][0]["text"]
        except Exception:
            return None


def _extract_prompt(row: Dict[str, Any]) -> Optional[str]:
    for key in ("input_text", "input", "attack_prompt", "prompt"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val
    prom = _join_user_messages(row.get("messages"))
    if prom:
        return prom
    ic = row.get("input_case")
    if isinstance(ic, dict):
        v = ic.get("attack_prompt")
        if isinstance(v, str) and v.strip():
            return v
    return None


def _extract_response(row: Dict[str, Any]) -> Optional[str]:
    for key in ("output_text", "output", "response", "model_output"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val
    raw = row.get("raw_output")
    txt = _openai_like(raw)
    if isinstance(txt, str) and txt.strip():
        return txt
    return None


def _read_model_seed(run_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    run_json = run_dir / "run.json"
    model = seed = None
    if run_json.exists():
        try:
            meta = json.loads(run_json.read_text(encoding="utf-8"))
            model = (
                meta.get("config", {}).get("provider", {}).get("model")
                or meta.get("provider_model")
                or meta.get("model")
            )
            seed = str(
                meta.get("config", {}).get("seed")
                or meta.get("seed")
                or ""
            ) or None
        except Exception:
            pass
    return model, seed


def _find_rows_file(run_dir: Path) -> Optional[Path]:
    direct = run_dir / "rows.jsonl"
    if direct.exists():
        return direct
    for candidate in run_dir.rglob("rows.jsonl"):
        if candidate.is_file():
            return candidate
    return None


def render_trial_io_table(run_dir: Path) -> str:
    rows_path = _find_rows_file(run_dir)
    if not rows_path:
        return "<p><em>No per-trial rows found (rows.jsonl missing).</em></p>"

    lines = []
    lines.append("<h2>Trial I/O (raw prompts &amp; responses)</h2>")
    lines.append("<p>Previews are truncated; expand a row to see the full text.</p>")
    lines.append(
        "<table style='width:100%; border-collapse:collapse'>"
        "<thead><tr>"
        "<th style='text-align:left; border-bottom:1px solid #ddd;'>#</th>"
        "<th style='text-align:left; border-bottom:1px solid #ddd;'>Attack prompt</th>"
        "<th style='text-align:left; border-bottom:1px solid #ddd;'>Model response</th>"
        "<th style='text-align:left; border-bottom:1px solid #ddd;'>Success</th>"
        "<th style='text-align:left; border-bottom:1px solid #ddd;'>Gate</th>"
        "</tr></thead><tbody>"
    )

    idx = 0
    for row in _read_jsonl_lines(rows_path):
        idx += 1
        prompt = _extract_prompt(row) or ""
        response = _extract_response(row) or ""
        success = row.get("success")
        pre = row.get("pre_gate")
        post = row.get("post_gate")
        pre_str = str(pre) if pre not in (None, "") else "-"
        post_str = str(post) if post not in (None, "") else "-"
        gate = esc(f"{pre_str}/{post_str}")
        success_str = "✅" if success is True else ("❌" if success is False else "–")

        lines.append(
            "<tr>"
            f"<td style='vertical-align:top; padding:6px 8px'>{idx}</td>"
            f"<td style='vertical-align:top; padding:6px 8px'>{preview_block(prompt)}</td>"
            f"<td style='vertical-align:top; padding:6px 8px'>{preview_block(response)}</td>"
            f"<td style='vertical-align:top; padding:6px 8px'>{success_str}</td>"
            f"<td style='vertical-align:top; padding:6px 8px'><code>{gate}</code></td>"
            "</tr>"
        )

    lines.append("</tbody></table>")
    return "\n".join(lines)


def _append_badges(run_dir: Path) -> str:
    model, seed = _read_model_seed(run_dir)
    bits = []
    if model:
        bits.append(
            "<span style='padding:2px 8px;border:1px solid #ddd;border-radius:12px;'>Model: "
            f"<code>{esc(model)}</code></span>"
        )
    if seed:
        bits.append(
            "<span style='padding:2px 8px;border:1px solid #ddd;border-radius:12px;margin-left:8px;'>Seed: "
            f"<code>{esc(seed)}</code></span>"
        )
    if not bits:
        return ""
    return "<p>" + " ".join(bits) + "</p>"


def _read_file_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_full_html(run_dir: Path) -> str:
    summary_svg = run_dir / "summary.svg"

    parts = []
    parts.append("<!doctype html><meta charset='utf-8'>")
    parts.append("<title>DoomArena-Lab Report</title>")
    parts.append(
        "<style>body{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Helvetica,Arial}"
        "table td,table th{font-size:12.5px}</style>"
    )
    parts.append("<h1>DoomArena-Lab Report</h1>")
    parts.append(_append_badges(run_dir))

    if summary_svg.exists():
        parts.append("<h2>Pass/Fail overview</h2>")
        parts.append(_read_file_safe(summary_svg))

    parts.append(render_trial_io_table(run_dir))

    parts.append("<h2>Artifacts</h2><ul>")
    for name in ("summary.csv", "summary.svg", "rows.jsonl", "run.json"):
        p = run_dir / name
        if p.exists():
            parts.append(f"<li><a href='{esc(str(name))}'>{esc(name)}</a></li>")
    parts.append("</ul>")

    return "\n".join(parts)


def main(run_dir_arg: str) -> int:
    run_dir = Path(run_dir_arg).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    index = run_dir / "index.html"
    try:
        html = build_full_html(run_dir)
        index.write_text(html, encoding="utf-8")
        return 0
    except Exception as e:
        index.write_text(f"<h1>Report (degraded)</h1><pre>{esc(e)}</pre>", encoding="utf-8")
        return 1


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python tools/mk_report.py <RUN_DIR>", file=sys.stderr)
        return 2
    return main(argv[1])


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
