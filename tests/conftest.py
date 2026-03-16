"""
Pytest configuration. handwerk_hamburg is imported from the installed package (pip install -e .).
"""

from pathlib import Path

# Project root (parent of tests/) for fixtures that need paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
