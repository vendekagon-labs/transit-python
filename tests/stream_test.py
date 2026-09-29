## Copyright 2014 Cognitect. All Rights Reserved.
## Copyright 2026 Vendekagon Labs LLC.
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##      http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS-IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

# Streaming reads (Reader.readeach) and writes of several values.
import os
import subprocess
import sys
import unittest
from io import BytesIO, StringIO

from transit import sosjson
from transit.reader import Reader
from transit.transit_types import Keyword
from transit.writer import Writer
from tests.helpers import PROTOCOLS, needs_msgpack

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)

VALUES = [1, "~tilde", [Keyword("abcd"), Keyword("abcd")],
          {Keyword("abcd"): 'quote " and backslash \\ é \U0001f600'},
          frozenset([1, 2]), None]


class Trickle:
    """A binary stream that returns at most n bytes per read, like a pipe
    that data is still arriving on."""
    def __init__(self, data, n):
        self.data = data
        self.n = n

    def read1(self, size=-1):
        chunk, self.data = self.data[:self.n], self.data[self.n:]
        return chunk


def write_all(protocol, values):
    io = BytesIO() if protocol == "msgpack" else StringIO()
    w = Writer(io, protocol)
    for v in values:
        w.write(v)
    return io.getvalue()


def expected(values):
    return [tuple(v) if isinstance(v, list) else v for v in values]


class ReadEachTest(unittest.TestCase):
    def test_json_chunk_sizes(self):
        for protocol in ("json", "json_verbose"):
            data = write_all(protocol, VALUES).encode("utf-8")
            # sizes that split escapes and multi-byte characters
            for n in (1, 2, 3, 7, len(data)):
                got = list(Reader(protocol).readeach(Trickle(data, n)))
                self.assertEqual(got, expected(VALUES), (protocol, n))

    @needs_msgpack
    def test_msgpack_chunk_sizes(self):
        data = write_all("msgpack", VALUES)
        for n in (1, 5, len(data)):
            got = list(Reader("msgpack").readeach(Trickle(data, n)))
            self.assertEqual(got, expected(VALUES), n)

    def test_text_stream(self):
        data = write_all("json", VALUES)
        self.assertEqual(list(Reader("json").readeach(StringIO(data))),
                         expected(VALUES))

    def test_whitespace_between_values(self):
        data = ' ["~#\'",1]\n\t{"~#\'":2}  \n'
        self.assertEqual(list(Reader("json").readeach(StringIO(data))), [1, 2])

    def test_eof_ends_iteration(self):
        self.assertEqual(list(Reader("json").readeach(StringIO(""))), [])

    @needs_msgpack
    def test_eof_ends_iteration_msgpack(self):
        self.assertEqual(list(Reader("msgpack").readeach(BytesIO(b""))), [])

    def test_truncated_value(self):
        with self.assertRaises(ValueError):
            list(sosjson.items(StringIO('[1,"a]')))

    def test_writer_writes_separate_values(self):
        # no separator (in particular no comma) between top level values
        self.assertEqual(write_all("json", [[1], [2]]), "[1][2]")
        self.assertEqual(write_all("json_verbose", [{"a": 1}, {"a": 1}]),
                         '{"a":1}{"a":1}')


class RoundtripScriptTest(unittest.TestCase):
    """bin/read-write is what transit-format's verify harness drives (through
    bin/roundtrip, a shell script; run directly, it also works on Windows)."""

    def roundtrip(self, protocol, data):
        return subprocess.run([sys.executable, os.path.join(REPO, "bin", "read-write"), protocol.replace("_", "-")],
                              input=data, capture_output=True, check=True, timeout=30,
                              env=dict(os.environ, PATH=os.path.dirname(sys.executable)
                                       + os.pathsep + os.environ.get("PATH", ""))).stdout

    def test_roundtrip_script(self):
        for protocol in PROTOCOLS:
            data = write_all(protocol, VALUES)
            if protocol != "msgpack":
                data = data.encode("utf-8")
            self.assertEqual(self.roundtrip(protocol, data), data, protocol)


if __name__ == "__main__":
    unittest.main()
