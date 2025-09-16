import csv, os, sys, pathlib, datetime
from pathlib import Path

TOPN = int(os.getenv("TOPN", "5"))
CSV_PATH = Path("results/summary.csv")
README = Path("README.md")
B = "<!-- TOPN:BEGIN -->"
E = "<!-- TOPN:END -->"
TITLE = "## Latest experiments — Top N by ASR"


def load_rows():
    if not CSV_PATH.exists():
        print(f"[topn] {CSV_PATH} not found; nothing to inject")
        return []
    with CSV_PATH.open() as f:
        r = csv.DictReader(f)
        rows = list(r)
    # robust parse
    for row in rows:
        try:
            row["asr"] = float(row.get("asr", 0))
        except Exception:
            row["asr"] = 0.0
        row["run_at"] = row.get("run_at", "")
    rows.sort(key=lambda x: (x["asr"], x["run_at"]), reverse=True)
    return rows[:TOPN]


def render_table(rows):
    if not rows:
        return "_No results yet._"
    cols = ["rank","exp_id","asr","mode","trials","seeds","git_commit","run_at"]
    out = ["|"+"|".join(["rank","exp_id","ASR","mode","trials","seeds","commit","run_at"])+"|",
           "|"+"|".join(["---"]*8)+"|"]
    for i, r in enumerate(rows, 1):
        out.append("|{}|{}|{:.3f}|{}|{}|{}|{}|{}|".format(
            i, r.get("exp_id",""), float(r["asr"]),
            r.get("mode",""), r.get("trials",""),
            r.get("seeds",""), (r.get("git_commit","") or "")[:7],
            r.get("run_at","")
        ))
    return "\n".join(out)


def inject(md, block):
    if B in md and E in md:
        pre = md.split(B)[0]
        post = md.split(E)[1]
        return f"{pre}{B}\n{TITLE}\n\n{block}\n{E}{post}"
    # append new section
    if not md.endswith("\n"):
        md += "\n"
    return md + f"\n{B}\n{TITLE}\n\n{block}\n{E}\n"


def main():
    rows = load_rows()
    table = render_table(rows)
    text = README.read_text(encoding="utf-8") if README.exists() else ""
    new = inject(text, table)
    if new != text:
        README.write_text(new, encoding="utf-8")
        print("[topn] README updated")
    else:
        print("[topn] No README change")


if __name__ == "__main__":
    main()
