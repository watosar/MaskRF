# SPDX-FileCopyrightText: 2026 watosar
# SPDX-License-Identifier: GPL-3.0-or-later

"""RF S-parameter simulation from binary metal masks with openEMS."""

from .api import CircuitResponse, SimulationError, evaluate_mask, load_response

__all__ = ["CircuitResponse", "SimulationError", "evaluate_mask", "load_response"]
