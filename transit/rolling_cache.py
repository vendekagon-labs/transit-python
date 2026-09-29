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

from transit.constants import SUB, MAP_AS_ARR

FIRST_ORD = 48
CACHE_CODE_DIGITS = 44
CACHE_SIZE = CACHE_CODE_DIGITS * CACHE_CODE_DIGITS
MIN_SIZE_CACHEABLE = 4


def is_cache_key(name):
    return len(name) > 0 and name[0] == SUB and name != MAP_AS_ARR


def encode_key(i):
    lo = i % CACHE_CODE_DIGITS
    hi = i // CACHE_CODE_DIGITS
    if hi == 0:
        return "^" + chr(lo + FIRST_ORD)
    return "^" + chr(hi + FIRST_ORD) + chr(lo + FIRST_ORD)


def decode_key(s):
    sz = len(s)
    if sz == 2:
        return ord(s[1]) - FIRST_ORD
    return (ord(s[2]) - FIRST_ORD) + \
           (CACHE_CODE_DIGITS * (ord(s[1]) - FIRST_ORD))


def is_cacheable(string, as_map_key=False):
    return len(string) >= MIN_SIZE_CACHEABLE \
        and (as_map_key or string[:2] in ("~#", "~$", "~:"))


class RollingCache:
    """This is the internal cache used by python-transit for cacheing and
    expanding map keys during writing and reading.  The cache enables transit
    to minimize the amount of duplicate data sent over the wire, effectively
    compressing down the overall payload size.  The cache is not intended to
    be used directly.

    Readers and writers must agree on cache codes, so this follows the
    transit spec (and transit-java): codes are assigned in order from "^0",
    and once CACHE_SIZE entries are in use the cache starts over from "^0".
    """
    def __init__(self):
        self.key_to_value = {}
        self.value_to_key = {}
        self.index = 0

    def decode(self, name, as_map_key=False):
        """Reading: expand a cache code, or remember a cacheable value.
        Always returns the (uncached) name.
        """
        if is_cache_key(name):
            try:
                return self.key_to_value[name]
            except KeyError:
                raise ValueError("Unknown cache code: " + name) from None
        if is_cacheable(name, as_map_key):
            self.encache(name)
        return name

    def encode(self, name, as_map_key=False):
        """Writing: returns the name the first time and the code after that."""
        if name in self.value_to_key:
            return self.value_to_key[name]
        if is_cacheable(name, as_map_key):
            self.encache(name)
        return name

    def size(self):
        return len(self.key_to_value)

    def is_cache_full(self):
        return self.index >= CACHE_SIZE

    def encache(self, name):
        if self.is_cache_full():
            self.clear()
        key = encode_key(self.index)
        self.index += 1
        self.key_to_value[key] = name
        self.value_to_key[name] = key
        return name

    def clear(self):
        self.key_to_value = {}
        self.value_to_key = {}
        self.index = 0
