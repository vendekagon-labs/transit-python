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

import itertools


def mapcat(f, i):
    return itertools.chain.from_iterable(map(f, i))


def pairs(i):
    return zip(*[iter(i)] * 2)


cycle = itertools.cycle


def take(n, i):
    return itertools.islice(i, 0, n)


def require_msgpack():
    """Import msgpack, which is only needed for the msgpack protocol."""
    try:
        import msgpack
    except ImportError as e:
        raise ImportError("The msgpack protocol requires the msgpack package; "
                          "install it with: pip install 'transit-python[msgpack]'") from e
    return msgpack
