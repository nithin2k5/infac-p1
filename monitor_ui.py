#!/usr/bin/env python3
"""Standalone entry point for the monitor UI."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from src.main import main
    main()



