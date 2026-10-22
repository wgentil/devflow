"""UTF-8 wire output without changing the caller's process-wide text streams."""
from __future__ import annotations

import sys
from typing import TextIO


def write_utf8(text: str, *, stream: TextIO | None = None) -> int:
    stream = sys.stdout if stream is None else stream
    data = text.encode('utf-8')
    buffer = getattr(stream, 'buffer', None)
    if buffer is not None:
        # Preserve ordering if the caller previously used the text wrapper.
        stream.flush()
        written = buffer.write(data)
        if written != len(data):
            raise OSError('incomplete UTF-8 protocol write')
        buffer.flush()
    else:
        if stream.write(text) != len(text):
            raise OSError('incomplete text protocol write')
        stream.flush()
    return len(data)
