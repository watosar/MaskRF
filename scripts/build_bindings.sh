#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/paths.sh"
work="$MASKRF_BUILD_DIR"
prefix="$MASKRF_OPENEMS_DIR"
mkdir -p "$work" "$prefix"
cd "$work"
root="$PWD"
for component in CSXCAD openEMS; do
 cd "$root/sources/openEMS-Project/$component/python"
 uv run --no-project --python "$root/.venv/bin/python" setup.py build_ext \
 -I"$prefix/include:$prefix/usr/include:$prefix/usr/include/hdf5/serial" \
 -L"$prefix/lib:$prefix/usr/lib/x86_64-linux-gnu" -R"$prefix/lib" bdist_wheel
 mkdir -p "$prefix/wheels"
 cp dist/*.whl "$prefix/wheels/"
 uv pip install --python "$root/.venv/bin/python" dist/*.whl
 done

uv pip install --python "$MASKRF_PYTHON" --reinstall "$prefix"/wheels/*.whl
