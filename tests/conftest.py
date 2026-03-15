"""
Pytest configuration: add project src to path so handwerk_hamburg can be imported.
"""

import sys
from pathlib import Path

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Add src so "import handwerk_hamburg" works
sys.path.insert(0, str(PROJECT_ROOT / "src"))
