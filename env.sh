#!/usr/bin/env bash
MASKRF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASKRF_NATIVE="${MASKRF_NATIVE:-$MASKRF_ROOT/.native}"
export LD_LIBRARY_PATH="$MASKRF_NATIVE/lib:$MASKRF_NATIVE/usr/lib/x86_64-linux-gnu:$MASKRF_NATIVE/usr/lib/x86_64-linux-gnu/hdf5/serial${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MPLCONFIGDIR="$MASKRF_ROOT/tmp/matplotlib"
