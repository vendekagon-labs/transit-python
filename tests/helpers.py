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

import os
import unittest

from transit.transit_types import Keyword, frozendict
from transit.helpers import cycle, take

def ints_centered_on(m, n=5):
    return tuple(range(m - n, m + n + 1))


def array_of_symbools(m, n=None):
    if n is None:
        n = m

    seeds = map(lambda x: Keyword("key"+str(x).zfill(4)), range(0, m))
    return take(n, cycle(seeds))


def hash_of_size(n):
    return frozendict(zip(array_of_symbools(n), range(0, n+1)))


def transit_format_dir():
    """transit-format is expected at $TRANSIT_FORMAT_DIR, checked out next to
    this repo, or (as CI does) inside it."""
    if os.environ.get("TRANSIT_FORMAT_DIR"):
        return os.environ["TRANSIT_FORMAT_DIR"]
    repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
    for d in (os.path.join(repo, os.pardir, "transit-format"), os.path.join(repo, "transit-format")):
        if os.path.isdir(d):
            return d
    return os.path.join(repo, os.pardir, "transit-format")


def exemplar_path(name):
    """Path to a transit-format exemplar file."""
    return os.path.join(transit_format_dir(), "examples", "0.8", "simple", name)


try:
    import msgpack  # noqa: F401
    HAVE_MSGPACK = True
except ImportError:
    HAVE_MSGPACK = False

needs_msgpack = unittest.skipUnless(HAVE_MSGPACK, "msgpack is not installed")

PROTOCOLS = ("json", "json_verbose") + (("msgpack",) if HAVE_MSGPACK else ())
