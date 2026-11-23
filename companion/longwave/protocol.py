"""Native Messaging framing, with a conservative input size limit."""

import json
import struct

from .model import UserError

MAX_MESSAGE = 64 * 1024


def read_exact(stream, size):
    result = bytearray()
    while len(result) < size:
        chunk = stream.read(size - len(result))
        if not chunk:
            raise UserError("invalid_message", "Incomplete message.")
        result.extend(chunk)
    return bytes(result)


def read_message(stream):
    first = stream.read(1)
    if not first:
        return None
    length = struct.unpack("=I", first + read_exact(stream, 3))[0]
    if not 0 < length <= MAX_MESSAGE:
        raise UserError("invalid_message", "Message exceeds the permitted size.")
    try:
        data = json.loads(read_exact(stream, length))
    except (ValueError, UnicodeError) as exc:
        raise UserError("invalid_message", "Invalid JSON message.") from exc
    if not isinstance(data, dict):
        raise UserError("invalid_message", "Message must be an object.")
    return data


def write_message(stream, value):
    body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(body) > 900_000:
        raise UserError("response_too_large", "Response is too large.")
    stream.write(struct.pack("=I", len(body)) + body)
    stream.flush()
