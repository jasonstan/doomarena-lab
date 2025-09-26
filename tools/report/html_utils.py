from __future__ import annotations

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
