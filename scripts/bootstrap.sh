#!/usr/bin/env bash
# Ubuntu 24.04, x86_64; requires uv, git, cmake, a C/C++ compiler, Python headers.
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
work="$project/tmp/native-build"
mkdir -p "$work" "$project/.native"
cd "$work"
if [ ! -e native ]; then ln -s "$project/.native" native; fi
mkdir -p logs sources apt/lists/partial apt/cache/archives/partial native
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r "$project/scripts/requirements-native.txt"
if [ ! -d sources/openEMS-Project/.git ]; then
 git clone --recursive --branch v0.0.36 https://github.com/thliebig/openEMS-Project.git sources/openEMS-Project
fi
[ "$(git -C sources/openEMS-Project rev-parse HEAD)" = d0d2e8dad8a02388f1919bbcdd29a67e9199dd2c ]
apt-get -o Dir::State::lists="$PWD/apt/lists" -o Dir::Cache="$PWD/apt/cache" update
apt-get -o Debug::NoLocking=1 -o Dir::State::lists="$PWD/apt/lists" -o Dir::Cache="$PWD/apt/cache" --download-only --no-install-recommends -y install libboost-all-dev libhdf5-dev libtinyxml-dev libvtk9-dev libcgal-dev
bash "$project/scripts/build_native.sh"
bash "$project/scripts/build_bindings.sh"
uv sync --project "$project" --locked --inexact
