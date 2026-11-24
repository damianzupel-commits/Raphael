"""Puente a raphael_core.compat.v1.harness."""

import importlib
import sys

import raphael_harness  # noqa: F401  (asegura el path a raphael-core)

sys.modules[__name__] = importlib.import_module("raphael_core.compat.v1.harness")
