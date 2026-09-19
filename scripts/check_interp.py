#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exit 0 when running under 64-bit CPython 3.11/3.12, else 40.

Kept in a separate file on purpose: setup.cmd probes interpreters with this
script so that no parentheses appear inside the batch FOR block.
"""
import sys

ok = sys.version_info[:2] in [(3, 11), (3, 12)] and sys.maxsize > 2**32
sys.exit(0 if ok else 40)
