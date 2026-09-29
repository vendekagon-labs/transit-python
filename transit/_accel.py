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

# The optional native extension (transit._native, built from transit-format-c).
# Reader and Writer use it when it's available, unless TRANSIT_PUREPYTHON is
# set; otherwise, or for anything it doesn't handle, they use pure Python.
import os

native = None
if not os.environ.get("TRANSIT_PUREPYTHON"):
    try:
        from transit import _native as native
    except ImportError:
        native = None

FORMATS = {"json": 0, "json_verbose": 1, "msgpack": 2}
