from pathlib import Path

import httpx
import pytest
from conftest import FAKE_CLIENT_SECRET, FAKE_TOKEN

from roomsync import cli
from roomsync.platform.panopto import PanoptoClient
from roomsync.settings import Settings

TOKEN_PATH = "/Panopto/oauth2/connect/token"


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == TOKEN_PATH:
        return httpx.Response(200, json={"access_token": FAKE_TOKEN})
    if request.url.params["pageNumber"] != "0":
        return httpx.Response(200, json={"Results": []})
    return httpx.Response(
        200,
        json={
            "Results": [
                {"Id": "00000000-0000-0000-0000-000000000204", "Name": "Room 204 recorder", "State": "Stopped"},
                {"Id": "00000000-0000-0000-0000-000000000310", "Name": "Room 310 recorder"},
            ]
        },
    )


def denied(request: httpx.Request) -> httpx.Response:
    if request.url.path == TOKEN_PATH:
        return httpx.Response(200, json={"access_token": FAKE_TOKEN})
    return httpx.Response(403)


def patch_transport(monkeypatch: pytest.MonkeyPatch, fn: object) -> None:
    def make_client(settings: Settings) -> PanoptoClient:
        return PanoptoClient(settings, http=httpx.AsyncClient(transport=httpx.MockTransport(fn)))  # type: ignore[arg-type]

    monkeypatch.setattr(cli, "make_client", make_client)


@pytest.mark.usefixtures("panopto_env")
def test_recorders_prints_table_and_unverified_footer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patch_transport(monkeypatch, handler)
    assert cli.main(["recorders", "--query", "Room"]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[0].split() == ["Id", "Name", "State"]
    assert "00000000-0000-0000-0000-000000000204  Room 204 recorder  Stopped" in captured.out
    assert any(line.startswith("00000000-0000-0000-0000-000000000310  Room 310 recorder") for line in lines)
    assert lines[-1] == "UNVERIFIED: grant type and scope not confirmed for this site"
    assert FAKE_CLIENT_SECRET not in captured.out + captured.err
    assert FAKE_TOKEN not in captured.out + captured.err


def test_recorders_requires_query(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        cli.main(["recorders"])
    assert info.value.code == 2
    assert "--query" in capsys.readouterr().err


def test_missing_settings_exit_2_and_name_variables(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["recorders", "--query", "Room"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    for name in ("ROOMSYNC_PANOPTO_BASE_URL", "ROOMSYNC_PANOPTO_CLIENT_ID", "ROOMSYNC_PANOPTO_CLIENT_SECRET"):
        assert name in captured.err


@pytest.mark.usefixtures("panopto_env")
def test_platform_error_exit_1_without_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patch_transport(monkeypatch, denied)
    assert cli.main(["recorders", "--query", "Room"]) == 1
    captured = capsys.readouterr()
    assert "403" in captured.err
    assert FAKE_CLIENT_SECRET not in captured.out + captured.err
    assert FAKE_TOKEN not in captured.out + captured.err


def test_no_subcommand_prints_help_and_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([]) == 2
    assert "recorders" in capsys.readouterr().err


EDGE_FIXTURES = Path(__file__).parent / "fixtures" / "edge"


def test_edge_events_prints_a_row(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["edge-events", "--from", str(EDGE_FIXTURES / "current_or_next.json")]) == 0
    out = capsys.readouterr().out
    assert "TEST-DEVICE-0001" in out
    assert "Room 204 lecture" in out


def test_edge_events_empty_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["edge-events", "--from", str(EDGE_FIXTURES / "events_empty.json")]) == 0
    assert capsys.readouterr().out.strip() == "No Edge events in this file."


def test_edge_events_needs_no_platform_settings(capsys: pytest.CaptureFixture[str]) -> None:
    # Reading a saved Edge file must work with no ROOMSYNC_ settings at all (conftest clears them).
    assert cli.main(["edge-events", "--from", str(EDGE_FIXTURES / "events_for_device.json")]) == 0
    assert capsys.readouterr().err == ""


def test_edge_events_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["edge-events", "--from", str(tmp_path / "nope.json")]) == 2
    assert "nope.json" in capsys.readouterr().err


def test_edge_events_malformed_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cli.main(["edge-events", "--from", str(bad)]) == 2
    assert "bad.json" in capsys.readouterr().err


def test_edge_events_wrong_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    devices_file = EDGE_FIXTURES / "devices.json"
    assert cli.main(["edge-events", "--from", str(devices_file)]) == 2
    assert "Not a known Edge events shape" in capsys.readouterr().err


def hostile(request: httpx.Request) -> httpx.Response:
    if request.url.path == TOKEN_PATH:
        return httpx.Response(200, json={"access_token": FAKE_TOKEN})
    if request.url.params["pageNumber"] != "0":
        return httpx.Response(200, json={"Results": []})
    row = {
        "Id": "00000000-0000-0000-0000-000000000204\x1b[2J",
        "Name": "Room 204 \x1b]52;c;cm0gLXJmIH4=\x07recorder",
        "State": "Stopped\x07",
    }
    return httpx.Response(200, json={"Results": [row]})


@pytest.mark.usefixtures("panopto_env")
def test_recorders_escapes_control_characters(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    patch_transport(monkeypatch, hostile)
    assert cli.main(["recorders", "--query", "Room"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out and "\x07" not in out
    assert "000000000204\\x1b[2J" in out
    assert "Room 204 \\x1b]52;c;cm0gLXJmIH4=\\x07recorder" in out


def test_format_table_escapes_cells_before_measuring_widths() -> None:
    lines = cli.format_table([["Id", "Name"], ["a\x07", "b"]])
    assert lines == ["Id     Name", "a\\x07  b"]
