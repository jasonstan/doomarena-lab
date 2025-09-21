import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class ArtifactCheck:
    kind: str
    path: Path
    size: int | None
    preview: str
    errors: List[str]

    @property
    def ok(self) -> bool:
        return not self.errors


_PREVIEW_LIMIT = 200


def escape_preview(text: str) -> str:
    """Return a safely escaped preview string."""
    return text.encode("unicode_escape", errors="replace").decode("ascii", errors="replace")


def load_text(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return len(data), text


def check_html(path: Path) -> ArtifactCheck:
    errors: List[str] = []
    size: int | None = None
    preview = ""

    if not path.is_file():
        errors.append("HTML artifact is missing or not a file")
        return ArtifactCheck("html", path, size, preview, errors)

    size, text = load_text(path)
    preview = escape_preview(text[:_PREVIEW_LIMIT])

    if size < 1024:
        errors.append(f"Expected HTML size ≥ 1024 bytes but found {size}")

    body_match = re.search(r"<body\b[^>]*>(.*?)</body>", text, re.IGNORECASE | re.DOTALL)
    if not body_match:
        errors.append("HTML does not contain a <body>...</body> section")
    else:
        body_content = body_match.group(1)
        if not re.search(r"\S", body_content):
            errors.append("HTML <body> section is empty or whitespace only")

    return ArtifactCheck("html", path, size, preview, errors)


def check_svg(path: Path) -> ArtifactCheck:
    errors: List[str] = []
    size: int | None = None
    preview = ""

    if not path.is_file():
        errors.append("SVG artifact is missing or not a file")
        return ArtifactCheck("svg", path, size, preview, errors)

    size, text = load_text(path)
    preview = escape_preview(text[:_PREVIEW_LIMIT])

    if size <= 200:
        errors.append(f"Expected SVG size > 200 bytes but found {size}")

    if not re.search(r"<\s*(path|rect|circle|line|polyline|polygon)\b", text, re.IGNORECASE):
        errors.append("SVG does not contain drawing elements (path/rect/circle/line/polyline/polygon)")

    return ArtifactCheck("svg", path, size, preview, errors)


def print_diagnostics(results: Iterable[ArtifactCheck]) -> None:
    for result in results:
        status = "OK" if result.ok else "ERROR"
        size_display = "unknown" if result.size is None else str(result.size)
        print(f"{status}: {result.kind.upper()} artifact {result.path} size={size_display} bytes")
        print(f"{result.kind.upper()} preview (first {_PREVIEW_LIMIT} chars, escaped): {result.preview}")
        for error in result.errors:
            print(f"{status}: {error}")
        if result.ok:
            print()


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate REAL HTML and SVG artifacts")
    parser.add_argument("--html", dest="html_paths", action="append", default=[], help="Path to an HTML artifact")
    parser.add_argument("--svg", dest="svg_paths", action="append", default=[], help="Path to an SVG artifact")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if not args.html_paths and not args.svg_paths:
        print("No artifacts specified for validation", file=sys.stderr)
        return 1

    results: List[ArtifactCheck] = []

    for html_path in args.html_paths:
        resolved = Path(html_path).expanduser().resolve()
        results.append(check_html(resolved))

    for svg_path in args.svg_paths:
        resolved = Path(svg_path).expanduser().resolve()
        results.append(check_svg(resolved))

    print_diagnostics(results)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
