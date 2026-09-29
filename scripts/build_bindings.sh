#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
work="$project/tmp/native-build"
mkdir -p "$work" "$project/.native"
cd "$work"
if [ ! -e native ]; then ln -s "$project/.native" native; fi
root="$PWD"
source "$project/env.sh"
for component in CSXCAD openEMS; do
 cd "$root/sources/openEMS-Project/$component/python"
 uv run --no-project --python "$root/.venv/bin/python" setup.py build_ext \
 -I"$project/.native/include:$project/.native/usr/include:$project/.native/usr/include/hdf5/serial" \
 -L"$project/.native/lib:$project/.native/usr/lib/x86_64-linux-gnu" -R"$project/.native/lib" bdist_wheel
 mkdir -p "$project/.native/wheels"
 cp dist/*.whl "$project/.native/wheels/"
 uv pip install --python "$root/.venv/bin/python" dist/*.whl
 done

uv sync --project "$project" --locked --inexact
uv pip install --python "$project/.venv/bin/python" "$project"/.native/wheels/*.whl
