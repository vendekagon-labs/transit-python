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

# The native extension (transit._native) is optional: set TRANSIT_PUREPYTHON=1
# to skip it, and if it fails to compile the package installs as pure Python
# (except when building wheels with cibuildwheel, where it must compile).
import os
import sysconfig

from setuptools import Extension, setup

C_SOURCES = ["transit_json.c", "transit_msgpack.c", "transit_read.c",
             "transit_util.c", "transit_value.c", "transit_write.c"]

ext_modules = []
options = {}
if not os.environ.get("TRANSIT_PUREPYTHON"):
    # The limited API gives one abi3 wheel per platform for Python 3.10+;
    # free-threaded builds don't support it.
    limited = not sysconfig.get_config_var("Py_GIL_DISABLED")
    ext_modules.append(Extension(
        "transit._native",
        sources=["transit/_native.c"] + ["csrc/" + f for f in C_SOURCES],
        include_dirs=["csrc"],
        define_macros=[("Py_LIMITED_API", "0x030A0000")] if limited else [],
        py_limited_api=limited,
        optional=not os.environ.get("CIBUILDWHEEL")))
    if limited:
        options["bdist_wheel"] = {"py_limited_api": "cp310"}

setup(ext_modules=ext_modules, options=options)
