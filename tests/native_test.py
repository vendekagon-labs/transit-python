## Copyright 2026 Vendekagon Labs LLC.
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##      http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

# The native extension reads and writes exactly what pure Python does.
import datetime
import math
import os
import unittest
from contextlib import contextmanager
from io import BytesIO, StringIO

from transit import _accel, reader, writer
from transit.transit_types import TaggedValue, frozendict
from tests.helpers import HAVE_MSGPACK, exemplar_path

FORMATS = {"json": ".json", "json_verbose": ".verbose.json", "msgpack": ".mp"}

# The one difference in what's written: transit-c writes a map with composite
# keys as ["~#cmap", ...] in JSON, where pure Python (like transit-java)
# writes {"~#cmap": ...}. Both are valid transit and read back the same.
CMAP_EXEMPLARS = {"cmap_null_key", "cmap_pathological", "map_vector_keys"}


@contextmanager
def pure():
    saved = reader.native, writer.native
    reader.native = writer.native = None
    try:
        yield
    finally:
        reader.native, writer.native = saved


def same(a, b):
    """Equal, and of the same types all the way down."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return (math.isnan(a) and math.isnan(b)) or (a == b and math.copysign(1, a) == math.copysign(1, b))
    if isinstance(a, tuple):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, frozendict):
        return len(a) == len(b) and all(k in b and same(v, b[k]) for k, v in a.items())
    if isinstance(a, frozenset):
        return a == b and sorted(map(repr, map(type, a))) == sorted(map(repr, map(type, b)))
    if isinstance(a, datetime.datetime):
        return a == b and a.tzinfo == b.tzinfo
    if isinstance(a, TaggedValue):
        return a.tag == b.tag and same(a.rep, b.rep)
    return a == b


def read(data, protocol):
    return reader.Reader(protocol).read(BytesIO(data) if isinstance(data, bytes) else StringIO(data))


def write(value, protocol):
    io = BytesIO() if protocol == "msgpack" else StringIO()
    writer.Writer(io, protocol).write(value)
    return io.getvalue()


def exemplar_names():
    d = os.path.dirname(exemplar_path("x"))
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".edn")) if os.path.isdir(d) else []


@unittest.skipIf(_accel.native is None, "the native extension isn't built")
@unittest.skipUnless(HAVE_MSGPACK, "msgpack is needed to compare with the pure msgpack implementation")
class NativeMatchesPureTest(unittest.TestCase):
    def test_extension_is_from_transit_c(self):
        self.assertRegex(_accel.native.transit_c_version, "^[0-9a-f]{7,}$")

    def test_exemplars(self):
        names = exemplar_names()
        if not names:
            self.skipTest("transit-format exemplars not found")
        for name in names:
            for protocol, ext in FORMATS.items():
                with open(exemplar_path(name + ext), "rb") as f:
                    data = f.read()
                if protocol != "msgpack":
                    data = data.decode("utf-8")
                native_value = read(data, protocol)
                with pure():
                    pure_value = read(data, protocol)
                self.assertTrue(same(native_value, pure_value), (name, protocol, "read"))
                for out in FORMATS:
                    native_out = write(pure_value, out)
                    with pure():
                        pure_out = write(pure_value, out)
                    if name in CMAP_EXEMPLARS and out != "msgpack":
                        self.assertTrue(same(read(native_out, out), read(pure_out, out)), (name, protocol, out))
                    else:
                        self.assertEqual(native_out, pure_out, (name, protocol, "written as " + out))

    def test_unsupported_types_are_written_by_python(self):
        class Str(str):
            pass
        self.assertEqual(write([Str("a")], "json"), '["a"]')

    def test_streams(self):
        values = [1, "~a", (frozenset([1]), 2.5)]
        for protocol in FORMATS:
            data = b"".join(write(v, protocol) if protocol == "msgpack" else write(v, protocol).encode()
                            for v in values)
            got = list(reader.Reader(protocol).readeach(BytesIO(data)))
            with pure():
                expected = list(reader.Reader(protocol).readeach(BytesIO(data)))
            self.assertTrue(same(tuple(got), tuple(expected)), protocol)


if __name__ == "__main__":
    unittest.main()
