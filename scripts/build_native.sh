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
for pkg in apt/cache/archives/*.deb; do dpkg-deb -x "$pkg" "$prefix"; done
uv run --no-project --python .venv/bin/python "$script_dir/repair_library_links.py" "$prefix"
export CMAKE_PREFIX_PATH="$prefix/usr:$prefix"
export CPLUS_INCLUDE_PATH="$prefix/usr/include:$prefix/usr/include/x86_64-linux-gnu"
export LIBRARY_PATH="$prefix/usr/lib/x86_64-linux-gnu"
for component in fparser CSXCAD openEMS; do
 cmake -U "*LIBRAR*" -S "sources/openEMS-Project/$component" -B "build/$component" \
 -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_BUILD_TYPE=Release \
 -DFPARSER_ROOT_DIR="$prefix" -DCSXCAD_ROOT_DIR="$prefix" \
 -DHDF5_C_COMPILER_EXECUTABLE=HDF5_C_COMPILER_EXECUTABLE-NOTFOUND \
 -DHDF5_INCLUDE_DIRS="$prefix/usr/include/hdf5/serial" \
 -DHDF5_C_LIBRARY_hdf5="$prefix/usr/lib/x86_64-linux-gnu/hdf5/serial/libhdf5.so" \
 -DHDF5_C_LIBRARY_hdf5_hl="$prefix/usr/lib/x86_64-linux-gnu/hdf5/serial/libhdf5_hl.so"
 cmake --build "build/$component" -j 4
 cmake --install "build/$component"
done
