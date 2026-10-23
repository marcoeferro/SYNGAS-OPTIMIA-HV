"""Humo del dashboard: la app arranca y la página inicial renderiza sin errores."""

from __future__ import annotations

from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = Path(__file__).resolve().parents[2] / "src" / "optimia_hv" / "dashboard" / "app.py"


def test_dashboard_arranca_sin_excepciones() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
