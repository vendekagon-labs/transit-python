# This library is no longer maintained. An unaffiliated fork exists at https://github.com/3wnbr1/transit-python2.

transit-python
==============

Transit is a format and set of libraries for conveying values between
applications written in different programming languages. The library provides
support for marshalling data to/from Python.

 * [Rationale](http://blog.cognitect.com/blog/2014/7/22/transit)
 * [API docs](http://cognitect.github.io/transit-python/)
  * [Mirrored for PyPI](http://pythonhosted.org/transit-python/)
 * [Specification](http://github.com/cognitect/transit-format)

This implementation's major.minor version number corresponds to the
version of the Transit specification it supports.

_NOTE: Transit is intended primarily as a wire protocol for transferring data between applications. If storing Transit data durably, readers and writers are expected to use the same version of Transit and you are responsible for migrating/transforming/re-storing that data when and if the transit format changes._

## Installation

```sh
pip install transit-python             # JSON and JSON-verbose
pip install 'transit-python[msgpack]'  # also msgpack, when running as pure Python
```

transit-python releases up to 0.8.302 support Python 2.7 and 3.5; later
releases, from this repository, support Python 3.10 and later.

The package includes a native extension, built from
[transit-c](https://github.com/vendekagon-labs/transit-c), that reads and
writes transit 4-15 times faster than pure Python, with identical results.
PyPI has wheels with it compiled for Linux, macOS and Windows (x86_64 and
ARM); elsewhere pip builds it from the source distribution if there's a C
compiler, and otherwise installs the package as pure Python. Set
`TRANSIT_PUREPYTHON=1` to use pure Python regardless (or, when installing
from source, to not build the extension).

The native extension reads and writes msgpack itself. Pure Python needs the
[msgpack](https://pypi.org/project/msgpack/) package for that, installed
with the `msgpack` extra; without it, creating a msgpack `Reader` or `Writer`
raises an `ImportError` saying so.

To install from GitHub:

```sh
pip install "transit-python[msgpack] @ git+https://github.com/vendekagon-labs/transit-python.git"
```

(add `@<tag or commit>` to the URL to pin a version, or use
`git+ssh://git@github.com/...` to install over SSH). In a `pyproject.toml` or
`requirements.txt`, use the same `transit-python @ git+https://...` form.

## Usage

```python
# io can be any Python file descriptor,
# like you would typically use with JSON's load/dump

from transit.writer import Writer
from transit.reader import Reader

writer = Writer(io, "json") # or "json-verbose", "msgpack"
writer.write(value)

reader = Reader("json") # or "msgpack"
val = reader.read(io)
```

For example:

```
>>> from transit.writer import Writer
>>> from transit.reader import Reader
>>> from io import StringIO
>>> io = StringIO()
>>> writer = Writer(io, "json")
>>> writer.write(["abc", 1234567890])
>>> s = io.getvalue()
>>> reader = Reader()
>>> vals = reader.read(StringIO(s))
```


To read a sequence of values as they arrive (e.g. from a pipe or socket),
use `readeach`, which yields each value as soon as it has been read and stops
at the end of the stream. A `Writer` can likewise write any number of values.

```python
reader = Reader("json")
for value in reader.readeach(sys.stdin.buffer):
    writer.write(value)
```


## Supported Python versions

 * 3.10 and later


## Type Mapping

### Typed arrays, lists, and chars

The [transit spec](https://github.com/cognitect/transit-format)
defines several semantic types that map to more general types in Python:

* lists map to Python Tuples
* typed arrays (ints, longs, doubles, floats, bools), chars and bytes are
  read as TaggedValues (e.g. `TaggedValue("ints", (1, 2, 3))`), so they
  are written back out unchanged

Use a TaggedValue to write these out if it will benefit a consuming
app e.g.:

```python
writer.write(TaggedValue("ints", [1,2,3]))
```

### Python's bool and int

In Python, bools are subclasses of int (that is, `True` is actually `1`).

```python
>>> hash(1)
1
>>> hash(True)
1
>>> True == 1
True
```

This becomes problematic when decoding a map that contains bool and
int keys.  The bool keys may be overridden (ie: you'll only see the int key),
and the value will be one of any possible bool/int keyed value.

```python
>>> {1: "Hello", True: "World"}
{1: 'World'}
```

To counter this problem, the latest version of Transit Python introduces a
Boolean type with singleton (by convention of use) instances of "true" and
"false." A Boolean can be converted to a native Python bool with bool(x) where
x is the "true" or "false" instance. Logical evaluation works correctly with
Booleans (that is, they override the __bool__ method and correctly evaluate
as true and false in simple logical evaluation), but uses of a Boolean as an
integer will fail.

### Default type mapping

|Transit type|Write accepts|Read returns|
|------------|-------------|------------|
|null|None|None|
|string|str|str|
|boolean|bool, transit\_types.Boolean|transit\_types.true, transit\_types.false|
|integer|int|int|
|decimal|float|float|
|keyword|transit\_types.Keyword|transit\_types.Keyword|
|symbol|transit\_types.Symbol|transit\_types.Symbol|
|big decimal|decimal.Decimal|decimal.Decimal|
|big integer|int|int|
|time|datetime (timezone aware)|datetime (UTC)|
|uri|transit\_types.URI|transit\_types.URI|
|uuid|uuid.UUID|uuid.UUID|
|char|transit\_types.TaggedValue|transit\_types.TaggedValue|
|array|list, tuple|tuple|
|list|transit\_types.TaggedValue|tuple|
|set|set, frozenset|frozenset|
|map|dict, transit\_types.frozendict|transit\_types.frozendict|
|bytes|transit\_types.TaggedValue|transit\_types.TaggedValue|
|shorts, ints, longs, floats, doubles, chars, bools|transit\_types.TaggedValue|transit\_types.TaggedValue|
|link|transit\_types.Link|transit\_types.Link|


## Development

### Setup

The tests read the exemplar files from
[transit-format](http://github.com/cognitect/transit-format), which is
expected to be checked out next to transit-python (or inside it, or set
`TRANSIT_FORMAT_DIR` to its location).

```sh
pip install -e '.[test]'
```

The `test` extra includes msgpack. The msgpack tests are skipped when it
isn't installed, so run the tests both with and without it.

### Running the tests

```sh
pytest
```

### Running the transit-format verify harness

transit-format's `bin/verify` drives `bin/roundtrip`, which runs with the
`python3` on your `PATH`, so activate an environment with transit-python's
dependencies installed first.

```sh
cd ../transit-format
bin/verify -impls python
```

### Benchmarks

```sh
python -m tests.seattle_benchmark
```

### The native extension

`transit/_native.c` wraps transit-c, whose sources are in `csrc/`, copied
from [transit-c](https://github.com/vendekagon-labs/transit-c) by
`bin/sync-transit-c` (which records the commit in `csrc/transit_c_version.h`);
change them there, not here. `pip install -e .` builds the extension in place.
The tests check that native and pure Python read and write identically;
run them both ways (`TRANSIT_PUREPYTHON=1 pytest` for pure Python).

`bin/verify` runs transit-format's verify harness in each encoding, with the
[clojure CLI](https://clojure.org/guides/install_clojure), and fails if any
roundtrip does.

### Releasing

The version is 0.8.<number of commits>. To release:

```sh
bin/make-release    # stamps the version into transit/__init__.py
git commit -am "Release 0.8.N"
git tag v0.8.N
git push origin main v0.8.N
```

Pushing the tag runs `.github/workflows/wheels.yml`, which tests, builds the
sdist and wheels (with [cibuildwheel](https://cibuildwheel.pypa.io)), and
publishes them to PyPI with trusted publishing.


## Contributing

This library is open source, developed internally by Cognitect. We welcome discussions of potential problems and enhancement suggestions on the [transit-format mailing list](https://groups.google.com/forum/#!forum/transit-format). Issues can be filed using GitHub [issues](https://github.com/cognitect/transit-python/issues) for this project. Because transit is incorporated into products and client projects, we prefer to do development internally and are not accepting pull requests or patches.

## Copyright and License

Copyright © 2026 Vendekagon Labs LLC

Copyright © 2014-2016 Cognitect

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
