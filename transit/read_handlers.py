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

import datetime
import re
import uuid
from decimal import Decimal

from transit import transit_types
from transit.helpers import pairs

## Read handlers are used by the decoder when parsing/reading in Transit
## data and returning Python objects

EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

_RFC3339 = re.compile(r"(\d{4}-\d\d-\d\d)[Tt ](\d\d:\d\d:\d\d)(?:\.(\d+))?"
                      r"([Zz]|[+-]\d\d:\d\d)?$")


def parse_rfc3339(s):
    """Parse an RFC 3339 timestamp into a UTC datetime, to the millisecond
    (transit times are points in time, with millisecond precision, as they
    are for the other transit implementations).

    Normalizes what datetime.fromisoformat can't handle on every supported
    Python ("Z", fractional seconds that aren't 3 or 6 digits). A missing
    offset is taken to be UTC.
    """
    m = _RFC3339.match(s)
    if not m:
        d = datetime.datetime.fromisoformat(s)
    else:
        date, time, frac, offset = m.groups()
        if frac:
            time += "." + frac[:6].ljust(6, "0")
        if offset is None or offset in "Zz":
            offset = "+00:00"
        d = datetime.datetime.fromisoformat(date + "T" + time + offset)
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    d = d.astimezone(datetime.timezone.utc)
    return d.replace(microsecond=d.microsecond // 1000 * 1000)


class DefaultHandler:
    @staticmethod
    def from_rep(t, v):
        return transit_types.TaggedValue(t, v)


class NoneHandler:
    @staticmethod
    def from_rep(_):
        return None


class KeywordHandler:
    @staticmethod
    def from_rep(v):
        return transit_types.Keyword(v)


class SymbolHandler:
    @staticmethod
    def from_rep(v):
        return transit_types.Symbol(v)


class BigDecimalHandler:
    @staticmethod
    def from_rep(v):
        return Decimal(v)


class BooleanHandler:
    @staticmethod
    def from_rep(x):
        return transit_types.true if x == "t" else transit_types.false


class IntHandler:
    @staticmethod
    def from_rep(v):
        return int(v)


class FloatHandler:
    @staticmethod
    def from_rep(v):
        return float(v)


class UuidHandler:
    @staticmethod
    def from_rep(u):
        """Given a string, or a pair of signed 64 bit ints (most significant
        first), return a UUID object."""
        if isinstance(u, str):
            return uuid.UUID(u)
        mask = (1 << 64) - 1
        return uuid.UUID(int=(u[0] & mask) << 64 | (u[1] & mask))


class UriHandler:
    @staticmethod
    def from_rep(u):
        return transit_types.URI(u)


class DateHandler:
    @staticmethod
    def from_rep(d):
        if isinstance(d, int):
            return DateHandler._convert_timestamp(d)
        if "T" in d:
            return parse_rfc3339(d)
        return DateHandler._convert_timestamp(int(d))

    @staticmethod
    def _convert_timestamp(ms):
        """Given a timestamp in ms, return a DateTime object."""
        return EPOCH + datetime.timedelta(milliseconds=ms)


class BigIntegerHandler:
    @staticmethod
    def from_rep(d):
        return int(d)


class LinkHandler:
    @staticmethod
    def from_rep(l):
        return transit_types.Link(**l)


class ListHandler:
    @staticmethod
    def from_rep(l):
        return l


class SetHandler:
    @staticmethod
    def from_rep(s):
        return frozenset(s)


class CmapHandler:
    @staticmethod
    def from_rep(cmap):
        return transit_types.frozendict(pairs(cmap))


class IdentityHandler:
    @staticmethod
    def from_rep(i):
        return i


class SpecialNumbersHandler:
    @staticmethod
    def from_rep(z):
        if z == 'NaN':
            return float('Nan')
        if z == 'INF':
            return float('Inf')
        if z == '-INF':
            return float('-Inf')
        raise ValueError("Don't know how to handle: " + str(z) + " as \"z\"")
