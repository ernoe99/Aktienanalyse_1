# 3. Klassen- und Funktionsdiagramme

## 3.1 Klassendiagramm

```mermaid
classDiagram
    direction LR

    class CurrencyConverter {
        +dict rates
        +dict historical_rates
        +str base_currency
        +datetime last_update
        +get_exchange_rate(from_currency, to_currency) float
        +get_historical_rates(from_currency, to_currency, period) DataFrame
        +convert_historical(df, price_columns, from_currency, to_currency) DataFrame
        +convert(amount, from_currency, to_currency) float
    }

    class StockAnalyzer {
        +str ticker
        +yf.Ticker stock
        +dict info
        +DataFrame history_5y
        +DataFrame history_1y
        +dict options_data
        +__init__(ticker)
        -_get_info() dict
        +get_history(period) DataFrame
        +is_etf() bool
        +get_holdings() DataFrame
        +get_key_metrics() dict
        +get_dividend_history_yearly() DataFrame
        +get_upcoming_dates() dict
        +calculate_moving_averages(df) DataFrame
        +calculate_bollinger_bands(df, window, num_std) DataFrame
        +calculate_macd(df) DataFrame
        +calculate_rsi(df, period) DataFrame
        +calculate_atr(df, period) DataFrame
        +calculate_historical_volatility(df, window) float
        +calculate_three_thumbs_rule() dict
        +get_options_info() dict
        +calculate_implied_volatility() dict
        +get_strategy_options() dict
        +get_seasonal_data() DataFrame
    }

    class yf_Ticker {
        <<extern: yfinance>>
        +info
        +history(period)
        +dividends
        +calendar
        +options
        +option_chain(date)
        +institutional_holders
        +major_holders
    }

    class retry_with_backoff {
        <<decorator>>
        max_retries = 3
        initial_delay = 2
        backoff_factor = 2
    }

    class SessionState {
        <<st.session_state>>
        +dict cached_analyzers
        +dict cache_timestamps
        +int api_call_count
        +dict options_loaded
    }

    StockAnalyzer *-- yf_Ticker : stock
    CurrencyConverter ..> yf_Ticker : FX-Ticker
    StockAnalyzer ..> retry_with_backoff : _get_info / get_history / get_options_info
    SessionState o-- "0..*" StockAnalyzer : cached_analyzers[ticker]
```

`currency_converter` ist eine **globale Singleton-Instanz** von `CurrencyConverter` auf Modulebene.

## 3.2 Datenstrukturen (Rückgabe-Dictionaries)

```mermaid
classDiagram
    direction TB
    class Metrics {
        <<dict: get_key_metrics>>
        name, sector, industry, currency, exchange, website
        current_price, previous_close, open, day_high, day_low
        52w_high, 52w_low
        market_cap, enterprise_value, volume, avg_volume, avg_volume_10d
        pe_ratio, forward_pe, price_to_book, price_to_sales, ev_to_ebitda
        revenue, revenue_growth, gross_margin, operating_margin, profit_margin
        ebitda, net_income, free_cash_flow, operating_cash_flow
        fcf_yield, price_to_fcf
        dividend_yield, dividend_rate, payout_ratio, ex_dividend_date
        beta, total_debt, debt_to_equity, current_ratio, quick_ratio
        earnings_date
    }
    class Thumbs {
        <<dict: calculate_three_thumbs_rule>>
        thumb1: value, description
        thumb2: value, description
        thumb3: value, description
        total_thumbs: int 0..3
        details: sma_200, price_vs_sma200, ytd_return,
                 first_5_days_return, january_return,
                 current_month, is_odd_year
    }
    class OptionsInfo {
        <<dict: get_options_info>>
        expiration_dates: list
        weekly, monthly, quarterly: list
        semi_annual, annual, leaps: list
        chains: dict[date, calls/puts DataFrame]
    }
    class Combination {
        <<dict: calculate_strategy_combinations>>
        long_call: strike, expiry, days, premium, iv, delta
        short_put: strike, expiry, days, premium, iv, otm_pct
        hedge_put: strike, expiry, days, premium, iv, otm_pct
        num_contracts, net_cost, max_risk, max_risk_chf
        premium_yield, vs_dividend
        capital_required, capital_required_chf
        upside_participation
    }
    class Signals {
        <<dict: calculate_short_call_signals>>
        macd_signal, sma200_signal, seasonality_signal
        combined_score, recommendation
        num_calls_to_sell, strike_recommendation
        details
    }
    class BacktestResult {
        <<dict: run_simple_backtest>>
        success, error, traceback
        data: list Tageswerte
        trades: list Transaktionen
        final_valuation, summary, warnings
    }
    Combination --> Signals : num_contracts
    Combination --> BacktestResult : Eingabe
```

## 3.3 Funktionsübersicht (Aufrufgraph)

```mermaid
flowchart LR
    main["main()"]

    subgraph UI["Anzeige"]
        d3["display_three_thumbs"]
        ddh["display_dividend_history"]
        doa["display_options_analysis"]
        dsb["display_strategy_builder"]
        dbt["display_backtest"]
        gs["generate_summary"]
        cpc["create_price_chart"]
        csc["create_seasonal_chart"]
    end

    subgraph LOGIK["Strategie & Backtest"]
        csco["calculate_strategy_combinations"]
        cscs["calculate_short_call_signals"]
        ces["calculate_exit_signals"]
        rsb["run_simple_backtest"]
        bs["black_scholes"]
        chv["calculate_historical_volatility"]
        gas["get_available_strikes"]
        fns["find_nearest_strike"]
        vs["validate_strike"]
        imo["is_market_open"]
    end

    subgraph SA["StockAnalyzer"]
        km["get_key_metrics"]
        ttr["calculate_three_thumbs_rule"]
        gh["get_history"]
        gud["get_upcoming_dates"]
        gdh["get_dividend_history_yearly"]
        goi["get_options_info"]
        civ["calculate_implied_volatility"]
        gso["get_strategy_options"]
        gsd["get_seasonal_data"]
        ind["calculate_* Indikatoren"]
    end

    CC["currency_converter"]
    FMT["format_number"]

    main --> km & ttr & gud & gh & gsd
    main --> d3 & ddh & doa & dsb & gs & cpc & csc
    main --> CC & FMT

    ddh --> gdh --> gh
    ttr --> gh
    gsd --> gh
    doa --> goi & civ & gso & gh & ind & CC
    civ --> goi
    gso --> goi
    cpc --> ind & CC
    dsb --> csco & cscs & ces & rsb & dbt & CC
    csco --> gso & CC
    cscs --> gh & ind & gsd
    rsb --> gh & gas & vs & bs & chv & fns & gsd & CC
    dbt --> imo
    gs --> FMT
    FMT --> CC
```

## 3.4 Sequenzdiagramm: „🔍 Analysieren“

```mermaid
sequenceDiagram
    autonumber
    actor U as Benutzer
    participant M as main()
    participant SS as session_state
    participant SA as StockAnalyzer
    participant Y as Yahoo Finance

    U->>M: Ticker eingeben + Analysieren
    M->>SA: StockAnalyzer(ticker)
    SA->>SA: sleep(2 s)
    SA->>Y: Ticker.info (mit Retry)
    Y-->>SA: info
    M->>SA: get_key_metrics()
    SA-->>M: metrics
    M->>SA: calculate_three_thumbs_rule()
    SA->>Y: history("2y")
    Y-->>SA: OHLCV
    SA-->>M: thumbs
    M->>SS: cached_analyzers[ticker], cache_timestamps[ticker]
    M-->>U: Kopfzeile (Kurs, Tagesänderung, 3-Daumen)
    par Rendern aller Reiter
        M->>SA: get_upcoming_dates() / get_dividend_history_yearly()
        SA->>Y: dividends, calendar, history("11y")
        M->>SA: get_history("5y"), get_history("1y")
        SA->>Y: history
        M->>SA: get_seasonal_data()
        SA->>Y: history("10y")
    end
    M-->>U: Reiter 1–5 (Reiter 6/7: Hinweis „Optionen laden“)
```

## 3.5 Sequenzdiagramm: „⚡ Optionen laden“ und Strategie-Builder

```mermaid
sequenceDiagram
    autonumber
    actor U as Benutzer
    participant M as main()
    participant DOA as display_options_analysis
    participant DSB as display_strategy_builder
    participant SA as StockAnalyzer
    participant Y as Yahoo Finance

    U->>M: ⚡ Optionen laden
    M->>M: options_loaded[ticker] = True
    M->>DOA: Reiter 6
    DOA->>SA: get_options_info()
    SA->>Y: Ticker.options
    loop bis zu 9 Verfalltermine
        SA->>Y: option_chain(exp)  (je 2 s Pause)
    end
    DOA->>SA: calculate_implied_volatility() / get_strategy_options()
    DOA-->>U: Termine, IV vs. HV, 4 Beine, Vergleich, Margin, Ketten
    M->>DSB: Reiter 7
    DSB->>DSB: calculate_strategy_combinations(target_risk)
    DSB->>DSB: calculate_short_call_signals(best.num_contracts)
    DSB->>DSB: calculate_exit_signals(best, Szenario) ×4
    DSB-->>U: Beste Kombination, Alternativen, Signale, Exit-Szenarien
    U->>DSB: 🔄 Backtest starten (Startdatum, Tage)
    DSB->>DSB: run_simple_backtest(...)
    DSB-->>U: display_backtest: Kennzahlen, Transaktionen, Charts
```

## 3.6 Ablaufdiagramm `main()`

```mermaid
flowchart TB
    A([Start / Rerun]) --> B["Session State initialisieren"]
    B --> C["Sidebar rendern:<br/>Ticker · Buttons · Währung · Chart-Typ · API-Status"]
    C --> D{"Analysieren oder<br/>Neu laden geklickt?"}
    D -->|ja| L["should_load = True<br/>(Neu laden: options_loaded = False)"]
    D -->|nein| E{"Ticker im Cache?"}
    E -->|ja, jünger 600 s| UC["use_cache = True"]
    E -->|ja, abgelaufen| L
    E -->|nein| G
    L --> LL["StockAnalyzer + Metriken + 3-Daumen laden<br/>→ Cache speichern"]
    LL -->|Fehler| ERR([Fehlermeldung + Tipps, Ende])
    LL --> G
    UC --> G
    G{"Optionen laden geklickt?"} -->|ja| OL["options_loaded[ticker] = True"]
    G -->|nein| H
    OL --> H{"Ticker im Cache?"}
    H -->|nein| W([Willkommensseite])
    H -->|ja| K["Kopfzeile: Ticker · Kurs · Tagesänderung · 3-Daumen"]
    K --> T["7 Reiter rendern"]
    T --> Z["Button Zusammenfassung erstellen"]
    Z --> ENDE([Ende])
```

## 3.7 Funktionsreferenz

### Modulebene

| Funktion | Parameter | Rückgabe | Beschreibung |
|---|---|---|---|
| `retry_with_backoff` | `max_retries=3, initial_delay=2, backoff_factor=2` | Decorator | Wiederholt nur bei Rate-Limit-Fehlern |
| `format_number` | `value, format_type='number'\|'currency'\|'percent'\|'ratio', from_currency, to_currency, symbol` | `str` | Formatiert mit T/B/M-Suffix und Umrechnung |
| `format_price` | `value, from_currency, to_currency` | `str` | Kurzform Preisformat |
| `create_price_chart` | `df, title, show_candles, fx_rate, currency_symbol, source_currency, target_currency` | `go.Figure` | 4 bzw. 5 Panels: Kurs+BB+SMA, (FX), Volumen, MACD, RSI |
| `create_seasonal_chart` | `seasonal_data, ticker` | `go.Figure` | Ø-Wochenrendite und Anteil positiver Wochen |
| `display_three_thumbs` | `thumbs_result` | – | 4 Karten mit Daumen und Gesamtbewertung |
| `display_dividend_history` | `analyzer, source_currency, target_currency, curr_symbol` | – | Tabelle 10 Jahre, Einzelzahlungen, Ø-Rendite |
| `display_options_analysis` | `analyzer, metrics, source_currency, target_currency, curr_symbol` | – | Reiter 6 komplett |
| `generate_summary` | `analyzer, metrics, thumbs` | `str` | Text-Report zum Download |
| `calculate_strategy_combinations` | `analyzer, metrics, target_risk=5000, source_currency, target_currency` | `dict` | Top-5-Kombinationen (siehe 2.5.5) |
| `calculate_short_call_signals` | `analyzer, metrics, num_base_contracts=1` | `dict` | MACD/SMA200/Saison-Score (siehe 2.5.6) |
| `calculate_exit_signals` | `combination, current_price, original_price` | `dict` | Exit-Aktionen je Bein (siehe 2.5.7) |
| `black_scholes` | `S, K, T, r, sigma, option_type='call'\|'put'` | `float` | Optionspreis |
| `calculate_historical_volatility` | `prices: Series, window=30` | `float` | Vol p.a. dezimal, [0.05, 1.0] |
| `get_available_strikes` | `analyzer` | `list` | Strikes der Kette (siehe Einschränkung #2) |
| `find_nearest_strike` | `price, available_strikes, direction='above'\|'below'` | `float` | Nächster Strike bzw. Standardraster |
| `is_market_open` | – | `(bool, str)` | NYSE/NASDAQ 9:30–16:00 ET, Mo–Fr |
| `validate_strike` | `strike, available_strikes` | `(bool, float)` | Existenzprüfung + nächster Strike |
| `run_simple_backtest` | `analyzer, combination, start_date, num_days, current_price, source_currency, target_currency` | `dict` | Simulation (siehe 2.5.9) |
| `display_backtest` | `result, curr_symbol, target_currency` | – | Kennzahlen, Transaktionen, B&S-Schlussbewertung, Charts, Tageswerte |
| `display_strategy_builder` | `analyzer, metrics, source_currency, target_currency, curr_symbol` | – | Reiter 7 komplett |
| `main` | – | – | Einstiegspunkt |

### `StockAnalyzer`

| Methode | Yahoo-Zugriff | Rückgabe |
|---|---|---|
| `__init__(ticker)` | `info` (über `_get_info`) | – |
| `_get_info()` | `Ticker.info` (Retry) | `dict` |
| `get_history(period)` | `Ticker.history` (Retry) | OHLCV-`DataFrame` |
| `is_etf()` | – | `quoteType == 'ETF'` |
| `get_holdings()` | `institutional_holders` → `major_holders` → `info['holdings']` | `DataFrame` |
| `get_key_metrics()` | – (aus `info`) | `dict` (siehe 3.2) |
| `get_dividend_history_yearly()` | `dividends`, `history("11y")` | Jahr, Gesamt, Anzahl, Jahresanfangskurs, Rendite %, Einzelzahlungen |
| `get_upcoming_dates()` | `dividends`, `calendar` | Ex-Dividende und Earnings (ggf. geschätzt) |
| `calculate_*` (Indikatoren) | – | `DataFrame` mit zusätzlichen Spalten |
| `calculate_three_thumbs_rule()` | `history("2y")` | `dict` (siehe 3.2) |
| `get_options_info()` | `options`, `option_chain` ×≤9 (Retry) | `dict` (siehe 3.2) |
| `calculate_implied_volatility()` | über `get_options_info` | `avg_call_iv, avg_put_iv, atm_iv, iv_percentile` |
| `get_strategy_options()` | über `get_options_info` | 4 Beine mit `expiration, options, days` |
| `get_seasonal_data()` | `history("10y")` | Week, Avg_Return, Std_Return, Count, Avg_Return_Pct, Positive_Pct |
