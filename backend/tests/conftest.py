import pytest
import sys
import os

# Ensure backend root is on path when running tests from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
