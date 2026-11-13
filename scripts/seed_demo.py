#!/usr/bin/env python3
"""Convenience entrypoint to seed the 3 reference agents and demo data.

Usage::

    uv run --package avaxagent-studio-backend python scripts/seed_demo.py
    # or via Makefile:
    make seed
"""

from __future__ import annotations

from app.seed import main

if __name__ == "__main__":
    main()
