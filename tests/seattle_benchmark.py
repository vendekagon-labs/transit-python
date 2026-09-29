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

from transit.reader import JsonUnmarshaler
import json
import time
from io import StringIO
import os

from tests.helpers import exemplar_path

def run_tests(data):
    datas = StringIO(data)
    t = time.time()
    JsonUnmarshaler().load(datas)
    et = time.time()
    datas = StringIO(data)
    tt = time.time()
    json.load(datas)
    ett = time.time()
    read_delta = (et - t) * 1000.0
    print("Done: " + str(read_delta) + "  --  raw JSON in: " + str((ett - tt) * 1000.0))
    return read_delta


seattle_dir = os.path.dirname(exemplar_path("")) + "/../"
means = {}
for jsonfile in [seattle_dir + "example.json", 
                 seattle_dir + "example.verbose.json"]:
    data = ""
    with open(jsonfile, encoding='utf-8') as fd:
        data = fd.read()

    print("-"*50)
    print("Running " + jsonfile)
    print("-"*50)

    runs = int(os.environ.get("RUNS", 200))
    deltas = [run_tests(data) for x in range(runs)]
    means[jsonfile] = sum(deltas)/runs

for jsonfile, mean in means.items():
    print("\nMean for" + jsonfile + ": "+str(mean))

