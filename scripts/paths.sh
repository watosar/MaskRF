#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

# Shared XDG locations; sourcing this file does not create directories.
case "${XDG_DATA_HOME:-}" in
 /*) MASKRF_DATA_HOME="$XDG_DATA_HOME" ;;
 *) MASKRF_DATA_HOME="$HOME/.local/share" ;;
esac
case "${XDG_CACHE_HOME:-}" in
 /*) MASKRF_CACHE_HOME="$XDG_CACHE_HOME" ;;
 *) MASKRF_CACHE_HOME="$HOME/.cache" ;;
esac
MASKRF_OPENEMS_DIR="$MASKRF_DATA_HOME/maskrf/openems-0.0.36"
MASKRF_BUILD_DIR="$MASKRF_CACHE_HOME/maskrf/openems-0.0.36"
export LD_LIBRARY_PATH="$MASKRF_OPENEMS_DIR/lib:$MASKRF_OPENEMS_DIR/usr/lib/x86_64-linux-gnu:$MASKRF_OPENEMS_DIR/usr/lib/x86_64-linux-gnu/hdf5/serial${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$MASKRF_CACHE_HOME/maskrf/matplotlib}"
