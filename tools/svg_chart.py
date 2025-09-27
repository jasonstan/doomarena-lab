"""Render compact SVG bar charts for attack success rates."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable, Sequence

__all__ = ["ChartBar", "render_compact_asr_chart"]


@dataclass(frozen=True)
class ChartBar:
    """Single bar entry describing successes over callable or total trials."""

    label: str
    successes: int
    callable_trials: int
    total_trials: int

    @property
    def denominator(self) -> int:
        """Return the divisor used for ASR (prefers callable trials)."""

        if self.callable_trials > 0:
            return self.callable_trials
        if self.total_trials > 0:
            return self.total_trials
        return 0

    @property
    def rate(self) -> float:
        denom = self.denominator
        if denom <= 0:
            return 0.0
        value = self.successes / float(denom)
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value


def render_compact_asr_chart(
    bars: Sequence[ChartBar] | Iterable[ChartBar],
    *,
    width: int = 720,
    bar_height: int = 18,
    gap: int = 10,
    left_padding: int = 16,
    right_padding: int = 72,
    top_padding: int = 28,
    bottom_padding: int = 20,
) -> str:
    """Render an SVG bar chart visualising ASR per slice/persona."""

    data = list(bars)
    if not data:
        height = top_padding + bottom_padding + bar_height
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>"
            "<rect width='100%' height='100%' fill='#f9fafb'/>"
            "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle'"
            " font-family='Inter,Segoe UI,sans-serif' font-size='14' fill='#6b7280'>"
            "No callable trials to chart"
            "</text></svg>"
        )

    max_label_length = max(len(bar.label) for bar in data)
    dynamic_label_width = max(140, min(width - right_padding - 160, max_label_length * 7))
    label_width = max(left_padding + 8, dynamic_label_width)
    track_width = max(80, width - label_width - right_padding)
    height = top_padding + bottom_padding + len(data) * bar_height + (len(data) - 1) * gap

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        "<rect width='100%' height='100%' rx='12' fill='#ffffff'/>",
        "<style>text{font-family:Inter,Segoe UI,sans-serif;font-size:12px;}</style>",
    ]

    grid_top = top_padding - 12
    grid_bottom = height - bottom_padding
    for pct in (0.0, 0.5, 1.0):
        x = label_width + pct * track_width
        lines.append(
            f"<line x1='{x:.2f}' x2='{x:.2f}' y1='{top_padding}' y2='{grid_bottom}' stroke='#e5e7eb' stroke-width='1'/>"
        )
        label = f"{pct * 100:.0f}%"
        lines.append(
            f"<text x='{x:.2f}' y='{grid_top}' text-anchor='middle' fill='#9ca3af' font-size='11'>{label}</text>"
        )

    for index, bar in enumerate(data):
        y = top_padding + index * (bar_height + gap)
        y_center = y + bar_height / 2
        label_text = escape(bar.label)
        lines.append(
            f"<text x='{left_padding}' y='{y_center:.2f}' dominant-baseline='middle' fill='#111827'>{label_text}</text>"
        )
        track_x = label_width
        lines.append(
            f"<rect x='{track_x:.2f}' y='{y:.2f}' width='{track_width:.2f}' height='{bar_height}' fill='#e5e7eb' rx='5'/>"
        )
        fill_width = track_width * bar.rate
        if fill_width > 0:
            lines.append(
                f"<rect x='{track_x:.2f}' y='{y:.2f}' width='{fill_width:.2f}' height='{bar_height}' fill='#2563eb' rx='5'/>"
            )
        ratio_denominator = bar.denominator
        if ratio_denominator <= 0:
            ratio_text = f"{bar.successes}/0"
        else:
            ratio_text = f"{bar.successes}/{ratio_denominator}"
        lines.append(
            f"<text x='{track_x + 8:.2f}' y='{y_center:.2f}' dominant-baseline='middle' fill='#1f2937' opacity='0.75' font-size='11'>{ratio_text}</text>"
        )
        percent_text = f"{bar.rate * 100:.1f}%"
        lines.append(
            f"<text x='{track_x + track_width + 8:.2f}' y='{y_center:.2f}' dominant-baseline='middle' fill='#111827'>{percent_text}</text>"
        )

    lines.append("</svg>")
    return "".join(lines)
