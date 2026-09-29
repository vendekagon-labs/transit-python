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

# msgpack is an optional dependency: everything but the msgpack protocol
# works without it, and asking for msgpack without it says how to get it.
import subprocess
import sys
import unittest
from io import BytesIO
from unittest import mock

from transit.reader import Reader
from transit.writer import Writer

WITHOUT_MSGPACK = """
import sys
sys.modules["msgpack"] = None  # makes "import msgpack" fail
from io import StringIO
from transit.reader import Reader
from transit.writer import Writer
for protocol in ("json", "json_verbose"):
    io = StringIO()
    Writer(io, protocol).write([1, {"a": 2}])
    assert Reader(protocol).read(StringIO(io.getvalue())) == (1, {"a": 2})
print("ok")
"""


class OptionalMsgpackTest(unittest.TestCase):
    def test_json_without_msgpack(self):
        out = subprocess.run([sys.executable, "-c", WITHOUT_MSGPACK],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(out.stdout.strip(), "ok", out.stderr)

    def test_msgpack_protocol_without_msgpack(self):
        with mock.patch.dict(sys.modules, {"msgpack": None}):
            for make in (lambda: Reader("msgpack"),
                         lambda: Writer(BytesIO(), "msgpack")):
                with self.assertRaises(ImportError) as cm:
                    make()
                self.assertIn("transit-python[msgpack]", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
