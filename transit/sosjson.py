## copyright 2014 cognitect. all rights reserved.
##
## licensed under the apache license, version 2.0 (the "license");
## you may not use this file except in compliance with the license.
## you may obtain a copy of the license at
##
##      http://www.apache.org/licenses/license-2.0
##
## unless required by applicable law or agreed to in writing, software
## distributed under the license is distributed on an "as-is" basis,
## without warranties or conditions of any kind, either express or implied.
## see the license for the specific language governing permissions and
## limitations under the license.
# Streaming reads of a sequence of JSON texts (as sent over a pipe or socket),
# yielding each top level value as soon as it has fully arrived.
#
# Rather than scanning a character at a time, whatever data is available is
# read in one go and a regex skips ahead to the characters that matter for
# finding the end of a value (brackets, quotes and escapes). Each complete
# value is then handed to json.loads.
import codecs
import json
import re

CHUNK_SIZE = 64 * 1024

_NON_WS = re.compile(r"[^ \t\n\r]")
_STRUCTURAL = re.compile(r'[\[\]{}"]')
_IN_STRING = re.compile(r'["\\]')


def read_available(stream, size=CHUNK_SIZE):
    """Return a function that reads whatever data is available from stream,
    blocking only until there is some. Returns an empty value at EOF.
    """
    buffer = getattr(stream, "buffer", None)
    if buffer is not None and hasattr(buffer, "read1"):
        # A text wrapper (e.g. sys.stdin); read(n) on it blocks until n
        # characters arrive, so read bytes from the underlying buffer.
        return lambda: buffer.read1(size)
    if hasattr(stream, "read1"):
        return lambda: stream.read1(size)
    return lambda: stream.read(size)


def chunks_raw(stream):
    """Yield data from stream as it becomes available, until EOF."""
    read = read_available(stream)
    while True:
        data = read()
        if not data:
            return
        yield data


def chunks(stream):
    """Yield text from stream as it becomes available, decoding bytes as UTF-8."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    for data in chunks_raw(stream):
        text = data if isinstance(data, str) else decoder.decode(data)
        if text:
            yield text
    decoder.decode(b"", final=True)  # raises on truncated UTF-8


def yield_json(stream):
    """Yield the text of each top level JSON array, object or string in stream."""
    buf = ""
    pos = 0          # where to resume scanning in buf
    start = None     # start of the value being read, None between values
    depth = 0
    in_string = False
    for text in chunks(stream):
        buf += text
        while True:
            if start is None:
                m = _NON_WS.search(buf, pos)
                if not m:
                    buf, pos = "", 0
                    break
                start = m.start()
                c = buf[start]
                pos = start + 1
                if c == '"':
                    in_string = True
                elif c in "[{":
                    depth = 1
                else:
                    raise ValueError("Expected a JSON array, object or string, "
                                     "found: " + repr(buf[start:start + 20]))
            elif in_string:
                m = _IN_STRING.search(buf, pos)
                if not m:
                    pos = len(buf)
                    break
                if m.group() == "\\":
                    if m.end() == len(buf):
                        # escaped character hasn't arrived yet
                        pos = m.start()
                        break
                    pos = m.end() + 1
                    continue
                pos = m.end()
                in_string = False
            else:
                m = _STRUCTURAL.search(buf, pos)
                if not m:
                    pos = len(buf)
                    break
                c = m.group()
                pos = m.end()
                if c == '"':
                    in_string = True
                    continue
                depth += 1 if c in "[{" else -1
            if depth == 0 and not in_string:
                yield buf[start:pos]
                buf, pos, start = buf[pos:], 0, None
    if start is not None:
        raise ValueError("Stream ended in the middle of a JSON value")


def items(stream, **kwargs):
    """Yield each top level JSON value in stream as soon as it is available.
    Keyword arguments are passed to json.loads (e.g. object_pairs_hook).
    """
    for s in yield_json(stream):
        yield json.loads(s, **kwargs)
