"""Rebuild the README art in docs/assets: the banner and the architecture diagram, each in light and dark.

Light and dark exist for GitHub's `<picture>` switch. The colors are the Epiphan Brand colors that the Epiphan Edge
Claude Kit's scripts/build_readme_art.py uses. The logos in docs/assets/epiphan-logo*.svg are copies of the
official Brand assets. This script embeds a logo's drawing unchanged and never rewrites those files.

The art shows only what the repo documents as planned or verified: everything is planned, a person approves a dry
run, and creating sessions on the platform comes last. It holds no real names, rooms, devices or dates. Update it
when the plan changes, and keep the image alt text in README.md in step with BANNER_LABEL and DIAGRAM_LABEL.

    python3 scripts/build_readme_art.py
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "docs" / "assets"
FONT = "Söhne,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
MONO = "Söhne Mono,ui-monospace,SFMono-Regular,Menlo,monospace"

LIGHT = {
    "bg": "#f1f2f0",
    "fg": "#111111",
    "muted": "#5a5a5a",
    "box": "#ffffff",
    "line": "#c9ccd4",
    "arrow": "#4a4aaf",
    "accent": "#0c3d34",
    "logo": "epiphan-logo-horizontal.svg",
}
DARK = {
    "bg": "#0d231f",
    "fg": "#ffffff",
    "muted": "#cfd3dc",
    "box": "#0c3d34",
    "line": "#316472",
    "arrow": "#d7daf9",
    "accent": "#6651fc",
    "logo": "epiphan-logo-horizontal-light.svg",
}
GREEN = "#83ce41"

BANNER_LABEL = "Epiphan roomsync: the schedule, the room device and the backup recording, in agreement"
DIAGRAM_LABEL = (
    "roomsync reads the video platform through its API and each Epiphan device through Epiphan Edge, saved as "
    "JSON, and reports where they disagree. A person approves a dry run before any session is created. Creating "
    "sessions comes last."
)


def logo_drawing(name: str) -> str:
    """The logo's drawing, without the XML declaration or its own <svg> wrapper."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", (ASSETS / name).read_text(encoding="utf-8"))
    return re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", svg.strip(), flags=re.DOTALL)


def banner(t: dict[str, str]) -> str:
    pills = []
    for i, label in enumerate(("Schedule", "Device", "Backup recording")):
        y = 28 + i * 44
        pills.append(
            f'<rect x="600" y="{y}" width="240" height="32" rx="8" fill="{t["accent"]}"/>\n'
            f'  <circle cx="620" cy="{y + 16}" r="6" fill="{GREEN}"/>\n'
            f'  <text x="634" y="{y + 21}" font-family="{FONT}" font-size="15" font-weight="600" '
            f'fill="#ffffff">{escape(label)}</text>'
        )
    pill_markup = "\n  ".join(pills)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="880" height="200" viewBox="0 0 880 200" role="img" aria-label="{escape(BANNER_LABEL)}">
  <rect width="880" height="200" rx="16" fill="{t["bg"]}"/>
  <svg x="30" y="14" width="180" height="50" viewBox="0 0 358.2 99.5">{logo_drawing(t["logo"])}</svg>
  <text x="48" y="120" font-family="{FONT}" font-size="36" font-weight="600" fill="{t["fg"]}">roomsync</text>
  <text x="50" y="158" font-family="{FONT}" font-size="19" fill="{t["muted"]}">Schedule, device and backup, in agreement</text>
  {pill_markup}
</svg>
"""


def node(x: int, y: int, w: int, h: int, title: str, sub: str, t: dict[str, str], *, mono: bool = False) -> str:
    font = f' font-family="{MONO}"' if mono else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{t["box"]}" stroke="{t["line"]}"/>\n  '
        f'<text x="{x + w / 2}" y="{y + h / 2 - 6}" text-anchor="middle" dominant-baseline="middle" font-size="14" '
        f'font-weight="600" fill="{t["fg"]}"{font}>{escape(title)}</text>\n  '
        f'<text x="{x + w / 2}" y="{y + h / 2 + 13}" text-anchor="middle" dominant-baseline="middle" font-size="12" '
        f'fill="{t["muted"]}">{escape(sub)}</text>'
    )


def arrow(x1: int, y1: int, x2: int, y2: int, t: dict[str, str], label: str = "") -> str:
    out = (
        f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{t["arrow"]}" stroke-width="2" fill="none" marker-end="url(#head)"/>'
    )
    if label:
        out += (
            f'\n  <text x="{(x1 + x2) / 2}" y="{min(y1, y2) - 9}" text-anchor="middle" font-size="11" '
            f'fill="{t["muted"]}">{escape(label)}</text>'
        )
    return out


def diagram(t: dict[str, str]) -> str:
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="350" viewBox="0 0 880 350" role="img" '
            f'aria-label="{escape(DIAGRAM_LABEL)}" font-family="{FONT}">'
        ),
        (
            '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{t["arrow"]}"/></marker></defs>'
        ),
        f'<rect width="880" height="350" rx="16" fill="{t["bg"]}"/>',
        node(30, 50, 200, 60, "Video platform", "Panopto first", t),
        arrow(230, 80, 338, 80, t, "API reads"),
        node(340, 50, 200, 60, "roomsync", "read only, dry run by default", t, mono=True),
        arrow(650, 80, 542, 80, t, "saved JSON"),
        node(650, 50, 200, 60, "Epiphan Edge", "read tools, through Claude Code", t),
        arrow(440, 112, 440, 158, t),
        node(340, 160, 200, 60, "Drift report", "where the two sides disagree", t),
        arrow(440, 222, 440, 268, t),
        node(340, 270, 200, 60, "A person approves", "the room, the time, the effect", t),
        (
            f'<path d="M338 300 L130 300 L130 114" stroke="{t["arrow"]}" stroke-width="2" stroke-dasharray="5 4" '
            'fill="none" marker-end="url(#head)"/>'
        ),
        f'<text x="234" y="292" text-anchor="middle" font-size="12" fill="{t["muted"]}">Create sessions</text>',
        f'<text x="234" y="321" text-anchor="middle" font-size="11" fill="{t["muted"]}">planned, built last</text>',
        f'<circle cx="590" cy="190" r="5" fill="{GREEN}"/>',
        f'<text x="602" y="195" font-size="13" fill="{t["fg"]}">Reads need no approval.</text>',
        "</svg>",
    ]
    return "\n  ".join(parts) + "\n"


def main() -> None:
    for name, theme in (("light", LIGHT), ("dark", DARK)):
        (ASSETS / f"banner-{name}.svg").write_text(banner(theme), encoding="utf-8")
        (ASSETS / f"architecture-{name}.svg").write_text(diagram(theme), encoding="utf-8")
    print(f"wrote banner and architecture art (light, dark) in {ASSETS}")


if __name__ == "__main__":
    main()
