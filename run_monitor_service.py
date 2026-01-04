#!/usr/bin/env python3
"""
Standalone script to run the background monitor service.
This can be used to test the service or run it manually.
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.background_monitor import main

if __name__ == "__main__":
    main()

