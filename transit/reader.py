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

import json

import msgpack

from transit import sosjson
from transit.decoder import Decoder


class Reader:
    """The top-level object for reading in Transit data and converting it to
    Python objects.  During initialization, you must specify the protocol used
    for unmarshalling the data- json or msgpack.
    """
    def __init__(self, protocol="json"):
        if protocol in ("json", "json_verbose"):
            self.reader = JsonUnmarshaler()
        elif protocol == "msgpack":
            self.reader = MsgPackUnmarshaler()
            self.unpacker = self.reader.unpacker
        else:
            raise ValueError("'" + protocol + "' is not a supported. " +
                             "Protocol must be:" +
                             "'json', 'json_verbose', or 'msgpack'.")

    def read(self, stream):
        """Given a readable file descriptor object (something `load`able by
        msgpack or json), read the data, and return the Python representation
        of the contents. One-shot reader.
        """
        return self.reader.load(stream)

    def register(self, key_or_tag, f_val):
        """Register a custom transit tag and decoder/parser function for use
        during reads.
        """
        self.reader.decoder.register(key_or_tag, f_val)

    def readeach(self, stream, **kwargs):
        """Read each object from stream as it becomes available, as a
        generator. Stops at the end of the stream.

        Data is read from stream as it arrives rather than waiting for a full
        buffer, so this works over pipes and sockets. For text streams wrapping
        a binary buffer (like sys.stdin), the underlying buffer is read.

        For msgpack, stream may be None, in which case the objects are taken
        from data fed to the `unpacker` property with `unpacker.feed()`.
        """
        for o in self.reader.loadeach(stream):
            yield o


class JsonUnmarshaler:
    """The top-level Unmarshaler used by the Reader for JSON payloads.  While
    you may use this directly, it is strongly discouraged.
    """
    def __init__(self):
        self.decoder = Decoder()

    def load(self, stream):
        return self.decoder.decode(json.load(stream))

    def loadeach(self, stream):
        for o in sosjson.items(stream):
            yield self.decoder.decode(o)


class MsgPackUnmarshaler:
    """The top-level Unmarshaler used by the Reader for MsgPack payloads.
    While you may use this directly, it is strongly discouraged.
    """
    def __init__(self):
        self.decoder = Decoder()
        self.unpacker = msgpack.Unpacker(strict_map_key=False)

    def load(self, stream):
        return self.decoder.decode(msgpack.unpack(stream, strict_map_key=False))

    def loadeach(self, stream):
        for o in self.unpacker:
            yield self.decoder.decode(o)
        if stream is None:
            return
        for data in sosjson.chunks_raw(stream):
            self.unpacker.feed(data)
            for o in self.unpacker:
                yield self.decoder.decode(o)
