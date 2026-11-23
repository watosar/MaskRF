#!/usr/bin/env bash
# Ubuntu 24.04, x86_64; requires uv, git, cmake, a C/C++ compiler, Python headers.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/paths.sh"
work="$MASKRF_BUILD_DIR"
if [ -z "${MASKRF_PYTHON:-}" ]; then
 project="$(dirname "$script_dir")"
 if [ -f "$project/pyproject.toml" ]; then
  uv sync --project "$project" --locked --inexact
  MASKRF_PYTHON="$project/.venv/bin/python"
 else
  MASKRF_PYTHON="$(uv run --no-project python -c 'import sys; print(sys.executable)')"
 fi
fi
export MASKRF_PYTHON
mkdir -p "$work" "$MASKRF_OPENEMS_DIR"
cd "$work"
mkdir -p logs sources apt/lists/partial apt/cache/archives/partial
if [ ! -x .venv/bin/python ]; then uv venv --python "$MASKRF_PYTHON" .venv; fi
uv pip install --python .venv/bin/python -r "$script_dir/requirements-native.txt"
if [ ! -d sources/openEMS-Project/.git ]; then
 git clone --recursive --branch v0.0.36 https://github.com/thliebig/openEMS-Project.git sources/openEMS-Project
fi
[ "$(git -C sources/openEMS-Project rev-parse HEAD)" = d0d2e8dad8a02388f1919bbcdd29a67e9199dd2c ]
apt-get -o Dir::State::lists="$PWD/apt/lists" -o Dir::Cache="$PWD/apt/cache" update
apt-get -o Debug::NoLocking=1 -o Dir::State::lists="$PWD/apt/lists" -o Dir::Cache="$PWD/apt/cache" --download-only --reinstall --no-install-recommends -y install libboost-all-dev libhdf5-dev libtinyxml-dev libvtk9-dev libcgal-dev
bash "$script_dir/build_native.sh"
bash "$script_dir/build_bindings.sh"
