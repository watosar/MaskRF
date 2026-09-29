#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
work="$project/tmp/native-build"
mkdir -p "$work" "$project/.native"
cd "$work"
if [ ! -e native ]; then ln -s "$project/.native" native; fi
root="$PWD"
for pkg in apt/cache/archives/*.deb; do dpkg-deb -x "$pkg" native; done
uv run --no-project --python .venv/bin/python "$project/scripts/repair_library_links.py"
source "$project/env.sh"
export CMAKE_PREFIX_PATH="$project/.native/usr:$project/.native"
export CPLUS_INCLUDE_PATH="$project/.native/usr/include:$project/.native/usr/include/x86_64-linux-gnu"
export LIBRARY_PATH="$project/.native/usr/lib/x86_64-linux-gnu"
for component in fparser CSXCAD openEMS; do
 cmake -U "*LIBRAR*" -S "sources/openEMS-Project/$component" -B "build/$component" \
 -DCMAKE_INSTALL_PREFIX="$project/.native" -DCMAKE_BUILD_TYPE=Release \
 -DFPARSER_ROOT_DIR="$project/.native" -DCSXCAD_ROOT_DIR="$project/.native" \
 -DHDF5_C_COMPILER_EXECUTABLE=HDF5_C_COMPILER_EXECUTABLE-NOTFOUND \
 -DHDF5_INCLUDE_DIRS="$project/.native/usr/include/hdf5/serial" \
 -DHDF5_C_LIBRARY_hdf5="$project/.native/usr/lib/x86_64-linux-gnu/hdf5/serial/libhdf5.so" \
 -DHDF5_C_LIBRARY_hdf5_hl="$project/.native/usr/lib/x86_64-linux-gnu/hdf5/serial/libhdf5_hl.so"
 cmake --build "build/$component" -j 4
 cmake --install "build/$component"
done
