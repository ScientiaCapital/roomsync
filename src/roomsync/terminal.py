"""Make text from a platform or a saved Edge file safe to print in a terminal.

Event titles, recorder names and ids are typed by other people. A control character in one could clear the screen,
set the clipboard (OSC 52), ring the bell or rewrite earlier output. Every C0 control (including ESC, so every
escape sequence and OSC), DEL and every C1 control is shown as a visible `\\xNN` escape instead of being sent raw.
"""

import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def safe_text(text: str) -> str:
    """`text` with each C0, DEL and C1 control character replaced by its `\\xNN` escape."""
    return _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)
