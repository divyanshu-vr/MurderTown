"""The report's charts: a rate at each value of one Rule, with its 95% interval, as SVG.

Drawn by hand rather than with a plotting library: one small chart type needs no dependency.
Colours follow the light or dark scheme of whoever views the chart; each point's tooltip and
the report's tables give the numbers.
"""

from dataclasses import dataclass
from html import escape

from mm.review.rates import Rate

WIDTH, HEIGHT = 560, 320
LEFT, RIGHT, TOP, BOTTOM = 56, 24, 48, 72
PLOT_WIDTH, PLOT_HEIGHT = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM

STYLE = """
svg { --surface: #fcfcfb; --text: #0b0b0b; --secondary: #52514e; --muted: #898781;
      --grid: #e1e0d9; --axis: #c3c2b7; --series: #2a78d6; }
@media (prefers-color-scheme: dark) {
  svg { --surface: #1a1a19; --text: #f0efec; --secondary: #c3c2b7; --muted: #898781;
        --grid: #2c2c2a; --axis: #383835; --series: #3987e5; }
}
text { font: 12px system-ui, -apple-system, "Segoe UI", sans-serif; fill: var(--secondary); }
.title { font-size: 14px; font-weight: 600; fill: var(--text); }
.muted { fill: var(--muted); }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--axis); stroke-width: 1; }
.interval { stroke: var(--series); stroke-width: 2; stroke-linecap: round; }
.point { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
"""


@dataclass(frozen=True)
class Point:
    """The rate at one value on the axis, from `games` games."""

    label: str
    rate: Rate
    games: int


def rate_chart(title: str, axis: str, points: list[Point]) -> str:
    """A chart of `title`: one point per value on the `axis`, with its interval."""
    step = PLOT_WIDTH / max(len(points), 1)
    parts = [
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="var(--surface)"/>',
        f'<text class="title" x="{LEFT}" y="24">{escape(title)}</text>',
        *_gridlines(),
        *(_point(point, LEFT + (index + 0.5) * step, axis) for index, point in enumerate(points)),
        f'<text x="{LEFT + PLOT_WIDTH / 2}" y="{HEIGHT - 8}" text-anchor="middle">'
        f"{escape(axis)}</text>",
    ]
    body = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{escape(title)}">\n'
        f"<style>{STYLE}</style>\n{body}\n</svg>\n"
    )


def _y(value: float) -> float:
    return TOP + (1 - value) * PLOT_HEIGHT


def _gridlines() -> list[str]:
    lines = []
    for value in (0, 0.25, 0.5, 0.75, 1):
        kind = "axis" if value == 0 else "grid"
        y = _y(value)
        lines += [
            f'<line class="{kind}" x1="{LEFT}" x2="{LEFT + PLOT_WIDTH}" y1="{y}" y2="{y}"/>',
            f'<text class="muted" x="{LEFT - 8}" y="{y + 4}" text-anchor="end">{value:.0%}</text>',
        ]
    return lines


def _point(point: Point, x: float, axis: str) -> str:
    below = TOP + PLOT_HEIGHT
    labels = (
        f'<text x="{x}" y="{below + 20}" text-anchor="middle">{escape(point.label)}</text>'
        f'<text class="muted" x="{x}" y="{below + 38}" text-anchor="middle">'
        f"{point.games} game{'' if point.games == 1 else 's'}</text>"
    )
    if point.rate.value is None or point.rate.interval is None:
        return labels
    low, high = point.rate.interval
    tooltip = (
        f"{axis} {point.label}: {point.rate.successes} of {point.rate.trials} "
        f"({point.rate.value:.0%}; 95% interval {low:.0%} to {high:.0%})"
    )
    return (
        f"<g><title>{escape(tooltip)}</title>"
        f'<line class="interval" x1="{x}" x2="{x}" y1="{_y(low)}" y2="{_y(high)}"/>'
        f'<line class="interval" x1="{x - 6}" x2="{x + 6}" y1="{_y(low)}" y2="{_y(low)}"/>'
        f'<line class="interval" x1="{x - 6}" x2="{x + 6}" y1="{_y(high)}" y2="{_y(high)}"/>'
        f'<circle class="point" cx="{x}" cy="{_y(point.rate.value)}" r="5"/></g>'
        f"{labels}"
    )
