#!/usr/bin/env bash
RF_REPRO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RF_REPRO_NATIVE="${RF_REPRO_NATIVE:-$RF_REPRO_ROOT/.native}"
export LD_LIBRARY_PATH="$RF_REPRO_NATIVE/lib:$RF_REPRO_NATIVE/usr/lib/x86_64-linux-gnu:$RF_REPRO_NATIVE/usr/lib/x86_64-linux-gnu/hdf5/serial${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MPLCONFIGDIR="$RF_REPRO_ROOT/tmp/matplotlib"
