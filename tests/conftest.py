import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "scripts"))


@pytest.fixture
def run_in_tmp(tmp_path, monkeypatch):
    """Change into a temporary working directory for CLI smoke tests."""

    monkeypatch.chdir(tmp_path)
    return tmp_path
