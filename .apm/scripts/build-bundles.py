#!/usr/bin/env python3
"""Compatibility shim for the renamed build-packages command."""

from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("build-packages.py")), run_name="__main__")
