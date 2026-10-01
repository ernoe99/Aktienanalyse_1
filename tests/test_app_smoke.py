"""
Smoke-Tests für die Streamlit-App (ohne Netzwerkzugriff auf Yahoo Finance nötig).

Ausführen:  pytest -q
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "Simple_stock_analyzer_go.py")


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file(APP, default_timeout=120).run()


def test_app_starts_without_exception(app):
    assert not app.exception


def test_sidebar_inputs_present(app):
    assert app.text_input[0].label == "Ticker-Symbol eingeben"
    assert app.text_input[0].value == "KO"
    labels = [b.label for b in app.button]
    assert "🔍 Analysieren" in labels
    assert "🔄 Neu laden" in labels
    assert "⚡ Optionen laden" in labels
    assert app.selectbox[0].label == "Anzeigewährung"
    assert app.selectbox[0].value == "CHF"
    assert app.radio[0].label == "Chart-Typ"


def test_black_scholes_put_call_parity():
    import importlib.util
    import math

    spec = importlib.util.spec_from_file_location("app_module", APP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    S, K, T, r, sigma = 100.0, 95.0, 0.5, 0.04, 0.25
    call = mod.black_scholes(S, K, T, r, sigma, "call")
    put = mod.black_scholes(S, K, T, r, sigma, "put")
    # Put-Call-Parität: C - P = S - K * e^(-rT)
    assert math.isclose(call - put, S - K * math.exp(-r * T), rel_tol=1e-6)
    # Verfall: innerer Wert
    assert mod.black_scholes(110, 100, 0, r, sigma, "call") == 10
    assert mod.black_scholes(90, 100, 0, r, sigma, "put") == 10
