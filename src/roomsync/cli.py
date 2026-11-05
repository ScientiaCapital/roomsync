"""roomsync command line. Every command here is read only."""

import argparse
import asyncio
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from roomsync.edge import format_events, load_json, parse_events
from roomsync.models import Recorder
from roomsync.platform.panopto import PanoptoClient, PanoptoError
from roomsync.settings import Settings, SettingsError, load_settings

UNVERIFIED_AUTH = "UNVERIFIED: grant type and scope not confirmed for this site"

Command = Callable[[argparse.Namespace], int]


def make_client(settings: Settings) -> PanoptoClient:
    """Build the Panopto client. Tests replace this to inject a mock transport."""
    return PanoptoClient(settings)


def format_table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Left-aligned columns separated by two spaces, header first."""
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return ["  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in rows]


async def _search_recorders(settings: Settings, query: str) -> list[Recorder]:
    async with make_client(settings) as client:
        return await client.search_recorders(query)


def _run_recorders(args: argparse.Namespace) -> int:
    settings = load_settings()
    recorders = asyncio.run(_search_recorders(settings, args.query))
    rows = [["Id", "Name", "State"]] + [[r.id, r.name, r.state or "-"] for r in recorders]
    for line in format_table(rows):
        print(line)
    print(UNVERIFIED_AUTH)
    return 0


def _add_recorders(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("recorders", help="list Panopto remote recorders that match a search")
    # The spec marks searchQuery required and does not say which query lists every recorder, so none is assumed.
    parser.add_argument("--query", required=True, help="Panopto searchQuery text, for example 'Room 204'")
    parser.set_defaults(func=_run_recorders)


async def _read_edge_events(path: Path) -> str:
    return format_events(parse_events(await load_json(path)))


def _run_edge_events(args: argparse.Namespace) -> int:
    try:
        table = asyncio.run(_read_edge_events(args.from_path))
    except (OSError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
        print(f"roomsync: {exc}", file=sys.stderr)
        return 2
    print(table)
    return 0


def _add_edge_events(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser("edge-events", help="print the events in a saved Epiphan Edge tool result")
    # Python can't call MCP tools (AGENTS.md rule 6): a Claude session saves the Edge JSON and passes the file here.
    parser.add_argument("--from", dest="from_path", type=Path, required=True, help="saved Edge events JSON file")
    parser.set_defaults(func=_run_edge_events)


def build_parser() -> argparse.ArgumentParser:
    """One `_add_<name>` function per subcommand; register a new one here."""
    parser = argparse.ArgumentParser(prog="roomsync", description="Read-only checks for a room schedule.")
    subparsers = parser.add_subparsers(title="commands", metavar="COMMAND")
    _add_recorders(subparsers)
    _add_edge_events(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command: Command | None = getattr(args, "func", None)
    if command is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        return command(args)
    except SettingsError as exc:
        print(exc, file=sys.stderr)
        return 2
    except PanoptoError as exc:
        print(f"roomsync: {exc}", file=sys.stderr)
        return 1
