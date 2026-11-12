import pytest

from roomsync.terminal import safe_text

CLEAR_SCREEN = "\x1b[2J"
OSC52_CLIPBOARD = "\x1b]52;c;cm0gLXJmIH4=\x07"
BELL = "\x07"


def has_control(text: str) -> bool:
    return any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in text)


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        (f"Room 204 {CLEAR_SCREEN}lecture", "Room 204 \\x1b[2Jlecture"),
        (f"Room 204 {OSC52_CLIPBOARD}", "Room 204 \\x1b]52;c;cm0gLXJmIH4=\\x07"),
        (f"Room 204{BELL}", "Room 204\\x07"),
        ("line\nbreak\ttab\rreturn", "line\\x0abreak\\x09tab\\x0dreturn"),
        ("c1 csi \x9b2J and osc \x9d0;t\x9c", "c1 csi \\x9b2J and osc \\x9d0;t\\x9c"),
        ("del \x7f", "del \\x7f"),
        ("plain Room 204 lecture, café", "plain Room 204 lecture, café"),
    ],
)
def test_safe_text_escapes_control_characters(raw: str, shown: str) -> None:
    assert safe_text(raw) == shown
    assert not has_control(safe_text(raw))
