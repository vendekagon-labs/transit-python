## Copyright 2014 Cognitect. All Rights Reserved.
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

# Readers and writers in different languages must assign cache codes the
# same way, including when the cache fills up and starts over. Python to
# Python roundtrips can't show that, so these check against the payloads
# transit-clj produces.
import json
import unittest
from io import BytesIO, StringIO

import msgpack

from transit.reader import Reader
from transit.rolling_cache import CACHE_SIZE, RollingCache, decode_key, encode_key
from transit.transit_types import Keyword
from transit.writer import Writer

N = CACHE_SIZE + 1


def keys(n):
    return [Keyword("key%04d" % i) for i in range(n)]


def wrapping_value():
    """A map with one more cacheable key than the cache holds, followed by
    maps reusing the last and first keys."""
    ks = keys(N)
    return [dict(zip(ks, range(N))),
            {ks[-1]: Keyword("last")},
            {ks[0]: Keyword("first")},
            {ks[-1]: Keyword("last-again")}]


# What transit-clj writes for wrapping_value(): the last key of the big map
# is the first entry after the cache starts over, so it is "^0", while key0000
# has been dropped and is written out again.
BIG = ["^ "] + [x for i in range(N) for x in ("~:key%04d" % i, i)]
WRAPPING_JSON = json.dumps([BIG,
                            ["^ ", "^0", "~:last"],
                            ["^ ", "~:key0000", "~:first"],
                            ["^ ", "^0", "~:last-again"]],
                           separators=(",", ":"))
WRAPPING_MSGPACK = msgpack.packb([dict(zip(BIG[1::2], BIG[2::2])),
                                  {"^0": "~:last"},
                                  {"~:key0000": "~:first"},
                                  {"^0": "~:last-again"}])


class CacheCodeTest(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(encode_key(0), "^0")
        self.assertEqual(encode_key(43), "^[")
        self.assertEqual(encode_key(44), "^10")
        self.assertEqual(encode_key(CACHE_SIZE - 1), "^[[")
        for i in range(CACHE_SIZE):
            self.assertEqual(decode_key(encode_key(i)), i)

    def test_starts_over_when_full(self):
        cache = RollingCache()
        for i in range(CACHE_SIZE):
            cache.encode("~:k%d" % i)
        self.assertEqual(cache.encode("~:k0"), "^0")
        self.assertEqual(cache.encode("~:new"), "~:new")
        self.assertEqual(cache.encode("~:new"), "^0")
        self.assertEqual(cache.encode("~:k0"), "~:k0")
        self.assertEqual(cache.encode("~:k0"), "^1")

    def test_unknown_code(self):
        with self.assertRaises(ValueError):
            RollingCache().decode("^0")


class CacheWrapInteropTest(unittest.TestCase):
    def test_write_json(self):
        io = StringIO()
        Writer(io, "json").write(wrapping_value())
        self.assertEqual(io.getvalue(), WRAPPING_JSON)

    def test_read_json(self):
        self.assertEqual(Reader("json").read(StringIO(WRAPPING_JSON)),
                         tuple(wrapping_value()))

    def test_read_msgpack(self):
        self.assertEqual(Reader("msgpack").read(BytesIO(WRAPPING_MSGPACK)),
                         tuple(wrapping_value()))

    def test_first_array_element_cached_once(self):
        # The first element of an array is inspected for a tag; it must still
        # only be added to the read cache once.
        payload = '[["~:aaaa","~:bbbb"],"^1"]'
        self.assertEqual(Reader("json").read(StringIO(payload)),
                         ((Keyword("aaaa"), Keyword("bbbb")), Keyword("bbbb")))


if __name__ == "__main__":
    unittest.main()
