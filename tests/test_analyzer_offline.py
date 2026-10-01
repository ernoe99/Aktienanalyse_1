"""
Offline-Tests mit simuliertem yfinance-Ticker (kein Netzwerk nötig).

Prüft:
- Daten-Cache im StockAnalyzer (Historie, Dividenden, Optionsketten)
- Backtest verwendet echte Strikes aus der Optionskette
- Zusammenfassung in Anzeigewährung
"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

APP = Path(__file__).resolve().parent.parent / "Simple_stock_analyzer_go.py"

PERIOD_DAYS = {"1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "11y": 4015}


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("app_offline", APP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _chain(strikes, kind):
    price = 100.0
    rows = []
    for k in strikes:
        intrinsic = max(0.0, price - k) if kind == "call" else max(0.0, k - price)
        mid = intrinsic + 2.0 + 0.02 * abs(price - k)
        rows.append({"strike": k, "lastPrice": mid, "bid": mid - 0.1, "ask": mid + 0.1,
                     "volume": 10, "openInterest": int(1000 - abs(price - k) * 5),
                     "impliedVolatility": 0.25})
    return pd.DataFrame(rows)


class FakeTicker:
    """Ersetzt yf.Ticker und zählt alle Datenabrufe."""

    def __init__(self, symbol):
        self.calls = {"history": 0, "dividends": 0, "calendar": 0, "options": 0, "option_chain": 0}
        self.info = {"currentPrice": 100.0, "previousClose": 99.0, "fiftyTwoWeekHigh": 120.0,
                     "fiftyTwoWeekLow": 80.0, "marketCap": 2e11, "dividendRate": 2.0,
                     "dividendYield": 0.02, "payoutRatio": 0.5, "currency": "USD",
                     "longName": "Test AG", "quoteType": "EQUITY"}
        today = datetime.now()
        self._exps = [(today + timedelta(days=d)).strftime("%Y-%m-%d")
                      for d in (7, 30, 100, 250, 500, 800)]
        self.strikes = {exp: [s for s in np.arange(60, 140.01, 2.5 if i else 1.0)]
                        for i, exp in enumerate(self._exps)}

    def history(self, period="5y"):
        self.calls["history"] += 1
        days = PERIOD_DAYS.get(period, 1825)
        idx = pd.bdate_range(end=datetime.now().date(), periods=int(days * 252 / 365))
        close = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, len(idx))))
        close = close / close[-1] * 100.0
        return pd.DataFrame({"Open": close * 0.999, "High": close * 1.01, "Low": close * 0.99,
                             "Close": close, "Volume": 1_000_000}, index=idx)

    @property
    def dividends(self):
        self.calls["dividends"] += 1
        idx = pd.date_range(end=datetime.now(), periods=12, freq="QS")
        return pd.Series(0.5, index=idx)

    @property
    def calendar(self):
        self.calls["calendar"] += 1
        return {}

    @property
    def options(self):
        self.calls["options"] += 1
        return tuple(self._exps)

    def option_chain(self, exp):
        self.calls["option_chain"] += 1
        strikes = self.strikes[exp]
        return SimpleNamespace(calls=_chain(strikes, "call"), puts=_chain(strikes, "put"))


@pytest.fixture
def analyzer(mod, monkeypatch):
    monkeypatch.setattr(mod, "RATE_LIMIT_DELAY", 0)
    monkeypatch.setattr(mod.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(mod.currency_converter, "get_exchange_rate",
                        lambda a, b: 1.0 if a == b else 0.9)
    return mod.StockAnalyzer("TEST")


def test_history_is_cached_and_copied(analyzer):
    h1 = analyzer.get_history("1y")
    h1.index = h1.index + pd.Timedelta(days=1)  # Aufrufer verändert die Kopie
    h2 = analyzer.get_history("1y")
    assert analyzer.stock.calls["history"] == 1
    assert not h1.index.equals(h2.index)


def test_dividends_and_calendar_cached(analyzer):
    analyzer.get_dividend_history_yearly()
    analyzer.get_upcoming_dates()
    analyzer.get_dividend_history_yearly()
    analyzer.get_upcoming_dates()
    assert analyzer.stock.calls["dividends"] == 1
    assert analyzer.stock.calls["calendar"] == 1


def test_options_loaded_once(analyzer):
    analyzer.get_options_info()
    analyzer.calculate_implied_volatility()
    analyzer.get_strategy_options()
    analyzer.get_options_info()
    assert analyzer.stock.calls["options"] == 1
    assert analyzer.stock.calls["option_chain"] == 6


def test_get_available_strikes(mod, analyzer):
    exps = analyzer.stock._exps
    weekly = mod.get_available_strikes(analyzer, exps[0], "calls")
    assert weekly == [float(s) for s in analyzer.stock.strikes[exps[0]]]
    assert mod.get_available_strikes(analyzer, "1999-01-01") == []
    assert len(mod.get_available_strikes(analyzer)) >= len(weekly)


def test_backtest_uses_real_chain_strikes(mod, analyzer):
    metrics = analyzer.get_key_metrics()
    combos = mod.calculate_strategy_combinations(analyzer, metrics, 5000, "USD", "CHF")
    best = combos["best_combination"]
    assert best is not None

    result = mod.run_simple_backtest(analyzer, best, datetime.now() - timedelta(days=120), 90,
                                     metrics["current_price"], "USD", "CHF")
    assert result["success"], result.get("error")
    assert result["warnings"] == []

    weekly_strikes = set(mod.get_available_strikes(analyzer, analyzer.stock._exps[0], "calls"))
    short_calls = [t for t in result["trades"] if t["type"] == "Short Call (Wöchentlich)"]
    assert short_calls
    assert all(t["strike"] in weekly_strikes for t in short_calls)
    # Keine zusätzlichen Yahoo-Abfragen durch den Backtest
    assert analyzer.stock.calls["option_chain"] == 6


def test_summary_in_display_currency(mod, analyzer):
    metrics = analyzer.get_key_metrics()
    thumbs = analyzer.calculate_three_thumbs_rule()
    text = mod.generate_summary(analyzer, metrics, thumbs, "USD", "CHF", "CHF ")
    assert "Aktueller Kurs:     CHF 90.00" in text
    assert "52-Wochen-Hoch:     CHF 108.00" in text
    assert "Dividende (p.a.):   CHF 1.80" in text
    assert "Marktkapitalisierung: CHF 180.00B" in text
    assert "$" not in text

    same = mod.generate_summary(analyzer, metrics, thumbs, "USD", "USD", "$")
    assert "Aktueller Kurs:     $100.00" in same
