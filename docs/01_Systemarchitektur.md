# 1. Systemarchitektur

## 1.1 Zweck des Systems

Das Tool unterstützt eine **Optionenstrategie zur Rentenergänzung** mit ca. 7-fachem Hebel. Es analysiert
Aktien und ETFs, bewertet sie mit der **3-Daumen-Regel**, stellt technische Charts dar und berechnet
eine **4-Bein-Optionskombination** inklusive Backtest:

| Bein | Richtung | Laufzeit | Zweck |
|---|---|---|---|
| 🔵 Long Call | Kauf | 6–12 Monate | Partizipation an Kurssteigerungen, Absicherung verkaufter Calls |
| 🔴 Short Put | Verkauf | 12–24 Monate | Basisposition, Prämieneinnahme |
| 🟡 Hedge Put | Kauf | 3–6 Monate | Absicherung des verkauften Puts |
| 🟢 Short Call | Verkauf | wöchentlich | Laufende Prämie auf ca. 50 % der Basispositionen |

## 1.2 Systemkontext

```mermaid
flowchart TB
    subgraph Nutzer
        B["👤 Anleger<br/>Webbrowser (Desktop / Mobil)"]
    end

    subgraph Laufzeit["Laufzeitumgebung (Cloud oder lokal)"]
        ST["Streamlit-Server<br/>Python 3.11"]
        APP["Simple_stock_analyzer_go.py<br/>v2.9"]
        SS[("st.session_state<br/>pro Browser-Sitzung")]
        FXC[("CurrencyConverter<br/>prozessweiter FX-Cache")]
        ST --> APP
        APP <--> SS
        APP <--> FXC
    end

    subgraph Extern["Externe Datenquelle"]
        YF["yfinance (Python-Bibliothek)"]
        YH[("Yahoo Finance<br/>HTTP-API")]
        YF --> YH
    end

    B <-->|"HTTPS / WebSocket"| ST
    APP -->|"Ticker.info, history,<br/>dividends, calendar,<br/>options, option_chain"| YF
    FXC -->|"FX-Ticker z.B. USDCHF=X"| YF
```

Das System ist **zustandslos gegenüber der Außenwelt**: Es gibt keine Datenbank, keine Benutzerkonten
und keine Secrets. Alle Daten werden bei Bedarf von Yahoo Finance geladen und im Speicher gecacht.

## 1.3 Schichtenmodell

Die Anwendung ist eine einzelne Python-Datei, logisch aber in vier Schichten gegliedert:

```mermaid
flowchart TB
    subgraph P["Präsentationsschicht (Streamlit UI)"]
        M["main()<br/>Sidebar · 7 Reiter · Zusammenfassung"]
        D["display_* Funktionen<br/>display_three_thumbs · display_dividend_history<br/>display_options_analysis · display_strategy_builder<br/>display_backtest"]
        C["Chart-Fabriken<br/>create_price_chart · create_seasonal_chart"]
    end

    subgraph L["Logikschicht (Analyse & Strategie)"]
        SA["StockAnalyzer<br/>Kennzahlen · Indikatoren · 3-Daumen<br/>Optionen · Saisonalität"]
        SB["Strategie-Funktionen<br/>calculate_strategy_combinations<br/>calculate_short_call_signals<br/>calculate_exit_signals"]
        BT["Backtest & Bewertung<br/>run_simple_backtest · black_scholes<br/>calculate_historical_volatility"]
    end

    subgraph U["Hilfsschicht"]
        F["format_number · format_price"]
        H["is_market_open · find_nearest_strike<br/>validate_strike · get_available_strikes"]
        CC["CurrencyConverter"]
    end

    subgraph I["Infrastruktur / Datenzugriff"]
        R["retry_with_backoff (Decorator)<br/>RATE_LIMIT_DELAY · MAX_RETRIES"]
        Y["yfinance.Ticker"]
    end

    M --> D --> C
    M --> SA
    D --> SA
    D --> SB --> SA
    D --> BT --> SA
    D --> F --> CC
    C --> CC
    BT --> H
    SA --> R --> Y
    CC --> Y
```

## 1.4 Deployment-Varianten

```mermaid
flowchart LR
    GH[("GitHub<br/>ernoe99/Aktienanalyse_1")]

    subgraph Cloud1["Streamlit Community Cloud"]
        SC["Container<br/>pip install -r requirements.txt<br/>streamlit run Simple_stock_analyzer_go.py"]
    end
    subgraph Cloud2["GitHub Codespaces"]
        CS["Dev Container<br/>python:3.11-bookworm<br/>Port 8501 weitergeleitet"]
    end
    subgraph CI["GitHub Actions"]
        GA["ci.yml<br/>py_compile + pytest"]
    end
    subgraph Lokal["Lokaler Rechner"]
        LO["venv + start_analyzer.sh<br/>http://localhost:8501"]
    end

    GH -->|"Auto-Deploy bei Push"| SC
    GH -->|".devcontainer/devcontainer.json"| CS
    GH -->|"push / pull_request"| GA
    GH -->|"git clone"| LO
```

| Variante | Einstieg | Konfiguration | Geeignet für |
|---|---|---|---|
| Streamlit Community Cloud | `Simple_stock_analyzer_go.py` | `requirements.txt`, `.streamlit/config.toml` | Dauerhafter Betrieb, Zugriff von überall |
| GitHub Codespaces | automatisch per `postAttachCommand` | `.devcontainer/devcontainer.json` | Entwicklung im Browser |
| Lokal (Linux/macOS) | `./start_analyzer.sh [port]` | `requirements.txt` | Offline-Entwicklung, eigene IP (weniger Rate-Limits) |
| CI | `.github/workflows/ci.yml` | `tests/` | Qualitätssicherung bei jedem Push |

Details: [05_Cloud_Deployment.md](05_Cloud_Deployment.md).

## 1.5 Datenfluss einer Analyse

```mermaid
flowchart LR
    T["Ticker-Eingabe"] --> A["StockAnalyzer(ticker)"]
    A --> I["info<br/>(Fundamentaldaten)"]
    A --> H["history<br/>1y · 2y · 5y · 10y · 11y"]
    A --> DV["dividends · calendar"]
    A --> O["options · option_chain<br/>(nur nach 'Optionen laden')"]

    I --> KM["get_key_metrics()"]
    H --> TT["calculate_three_thumbs_rule()"]
    H --> IND["Indikatoren<br/>SMA · BB · MACD · RSI · ATR"]
    H --> SE["get_seasonal_data()"]
    DV --> DH["get_dividend_history_yearly()<br/>get_upcoming_dates()"]
    O --> OA["get_options_info()<br/>get_strategy_options()<br/>calculate_implied_volatility()"]

    KM & TT --> HDR["Kopfzeile + Reiter Kennzahlen"]
    IND --> CH["Reiter Chart 5J / 1J"]
    SE --> SZ["Reiter Saisonalität"]
    DH --> HDR
    OA --> OPT["Reiter Optionsanalyse"]
    OA & IND & SE --> SBU["Reiter Strategie-Builder<br/>+ Backtest"]

    FX["CurrencyConverter"] -.->|"Umrechnung<br/>USD → CHF/EUR"| HDR & CH & OPT & SBU
```

## 1.6 Caching und Rate-Limiting-Architektur

Yahoo Finance begrenzt die Anzahl Anfragen pro IP. Auf Streamlit Cloud teilen sich viele Apps
dieselben ausgehenden IP-Adressen, daher ist der Schutz dort besonders wichtig.

```mermaid
flowchart TB
    subgraph E1["Ebene 1 – Sitzungs-Cache (st.session_state)"]
        C1["cached_analyzers[ticker]<br/>= analyzer, metrics, thumbs"]
        C2["cache_timestamps[ticker]<br/>gültig CACHE_TTL = 600 s"]
        C3["options_loaded[ticker]<br/>Optionsdaten nur auf Anforderung"]
    end
    subgraph E2["Ebene 2 – Prozess-Cache (CurrencyConverter)"]
        F1["rates – aktueller Kurs, 1 h"]
        F2["historical_rates – je Paar + Zeitraum"]
        F3["Fallback-Kurse fest im Code"]
    end
    subgraph E3["Ebene 3 – Drosselung & Wiederholung"]
        R1["time.sleep(RATE_LIMIT_DELAY = 2.0 s)<br/>vor jedem Yahoo-Aufruf"]
        R2["retry_with_backoff<br/>3 Versuche · 2 s → 4 s → 8 s<br/>nur bei 'rate limit' / 'too many'"]
    end
    E1 --> E2 --> E3 --> Y[("Yahoo Finance")]
```

| Mechanismus | Wo | Wirkung |
|---|---|---|
| Sitzungs-Cache | `main()` | Erneutes Rendern nutzt dasselbe `StockAnalyzer`-Objekt (keine neue `info`-Abfrage) |
| Getrenntes Laden der Optionen | Button **⚡ Optionen laden** | Optionsketten (bis zu 9 Abfragen) werden erst auf Wunsch geladen |
| FX-Cache | `CurrencyConverter` | Wechselkurse werden prozessweit wiederverwendet |
| Drosselung | `RATE_LIMIT_DELAY` | Mindestabstand zwischen Anfragen |
| Exponentielles Backoff | `retry_with_backoff` | Automatischer Neuversuch bei Rate-Limit-Fehlern |

> **Hinweis:** Der Sitzungs-Cache speichert das Analyzer-Objekt, **nicht** die Kurshistorien und
> Optionsketten. Diese werden bei jedem Neuaufbau der Seite (jede Widget-Interaktion) erneut geladen.
> Siehe [Software Design – Bekannte Einschränkungen](02_Software_Design.md#28-bekannte-einschränkungen-und-verbesserungspotenzial).

## 1.7 Technologie-Stack

| Komponente | Bibliothek | Mindestversion | Verwendung |
|---|---|---|---|
| Web-UI | `streamlit` | 1.28 | Oberfläche, Widgets, Session State, Tabs |
| Marktdaten | `yfinance` | 0.2.31 | Kurse, Fundamentaldaten, Dividenden, Optionsketten, FX |
| Datenverarbeitung | `pandas`, `numpy` | 2.0 / 1.24 | Zeitreihen, Indikatoren, Aggregationen |
| Charts | `plotly` | 5.18 | Interaktive Kerzen-/Linien-Charts, Subplots |
| Statistik | `scipy` | 1.11 | Normalverteilung `norm.cdf` für Black-Scholes |
| Zeitzonen | `pytz` | 2023.3 | US-Eastern-Zeit für Börsenöffnungszeiten |
| Laufzeit | Python | 3.11 empfohlen (≥ 3.9) | |
