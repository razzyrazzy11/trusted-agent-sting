import contextlib
import io
import os
import sys
from pathlib import Path

import pytest

LB_ROOT = Path(__file__).resolve().parents[1] / "Collusion_Liars_Bar"
if str(LB_ROOT) not in sys.path:
    sys.path.insert(0, str(LB_ROOT))


@pytest.fixture(autouse=True)
def _cwd_lb_root(monkeypatch):
    """The harness reads prompts/ relative to the working directory."""
    monkeypatch.chdir(LB_ROOT)


@pytest.fixture
def quiet():
    """Silence the harness's console output."""
    @contextlib.contextmanager
    def _q():
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    return _q
