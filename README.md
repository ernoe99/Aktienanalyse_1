# 📊 Aktienanalyse für Optionenstrategie

Ein umfassendes Streamlit-basiertes Analyse-Tool für Aktien und ETFs, optimiert für eine Optionenstrategie zur Generierung von Zusatzrente.

**Aktuelle Version:** 2.9 – `Simple_stock_analyzer_go.py` · 📚 **[Vollständige Dokumentation](docs/README.md)**
(Systemarchitektur, Software Design, Klassen-/Funktionsdiagramme, Bedienungsanleitung, Cloud-Deployment)

## 🎯 Ziel der Strategie

Das Tool unterstützt eine Optionenstrategie mit ca. 7-fachem Hebel:
- **Verkaufte Puts (langlaufend)**: Basisposition
- **Verkaufte Calls (wöchentlich)**: 30-50% des Bestandes, kurzfristige Prämieneinnahme
- **Gekaufte Calls (langlaufend)**: Absicherung der verkauften Calls + Partizipation an Kurssteigerungen
- **Gekaufte Puts (mittelfristig)**: Absicherung der verkauften Puts

## 📋 Features

### 7 Analyse-Reiter:

1. **Holdings**: Zeigt ETF-Bestandteile oder Unternehmensinfos bei Einzelaktien
2. **Kennzahlen**: Alle wichtigen Metriken inkl. 3-Daumen-Regel und 10-Jahres-Dividendenhistorie
3. **Chart 5 Jahre**: Kurs mit Bollinger, SMA200, MACD, RSI
4. **Chart 1 Jahr**: Detaillierte 1-Jahres-Ansicht
5. **Saisonalität**: Wöchentliche saisonale Muster (10 Jahre)
6. **Optionsanalyse**: IV, Strike-Empfehlungen, Optionsketten (separat ladbar)
7. **Strategie-Builder**: Optimale 4-Bein-Kombination, Short-Call-Signale, Exit-Signale, Backtest (separat ladbar)

### Weitere Funktionen:
- Anzeigewährung CHF / USD / EUR mit historischer Wechselkursumrechnung
- Sitzungs-Cache (10 Min.) und Rate-Limiting-Schutz für Yahoo Finance

### Kennzahlen:
- Marktkapitalisierung, Umsatz, PE Ratio, FCF Ratio
- Dividendenrendite (aktuell + 10-Jahres-Durchschnitt)
- Beta, Debt/Equity, Current Ratio
- Implied Volatility vs. Historische Volatilität
- Earnings- und Ex-Dividenden-Termine
- ATR für Strike-Auswahl

### 3-Daumen-Regel:
1. ☝️ Kurs über 200-Tage-Linie
2. ✌️ Year-to-Date positiv
3. 🤟 Jahresregel:
   - Ungerades Jahr: Erste 5 Tage positiv = positiv
   - Gerades Jahr: 70% erste 5 Tage + 30% gerades Jahr

## ☁️ Cloud (Streamlit Community Cloud)

1. <https://share.streamlit.io> → **Create app** → Repository `ernoe99/Aktienanalyse_1`, Branch `main`
2. **Main file path:** `Simple_stock_analyzer_go.py`, Python 3.11
3. **Deploy** – danach wird jeder Push automatisch ausgerollt

Alternativ im Browser über **GitHub Codespaces** (Dev Container startet die App automatisch).
Details: [docs/05_Cloud_Deployment.md](docs/05_Cloud_Deployment.md)

## 🚀 Lokale Installation

```bash
git clone https://github.com/ernoe99/Aktienanalyse_1.git
cd Aktienanalyse_1

# Variante A: Startskript (legt venv an, installiert, startet)
./start_analyzer.sh

# Variante B: manuell
pip install -r requirements.txt
streamlit run Simple_stock_analyzer_go.py
```

Tests: `pip install pytest && pytest -q`

## 📖 Verwendung

1. **Ticker eingeben**: z.B. `KO` (Coca-Cola), `AAPL` (Apple), `SPY` (S&P 500 ETF)
2. **Analysieren klicken**: Lädt alle Daten
3. **Durch die Reiter navigieren**: Verschiedene Analysen erkunden
4. **⚡ Optionen laden**: Aktiviert Optionsanalyse und Strategie-Builder
5. **Zusammenfassung erstellen**: Für späteres Nachschlagen

Alle Eingabefelder und Parameter: [docs/04_Bedienungsanleitung.md](docs/04_Bedienungsanleitung.md)

## 🛠️ Technische Details

- **Datenquelle**: Yahoo Finance (yfinance)
- **Charts**: Plotly (interaktiv)
- **UI**: Streamlit
- **Sprache**: Python 3.11 empfohlen
- **Frühere Versionen**: im Ordner [`legacy/`](legacy/README.md)

## ⚠️ Disclaimer

Diese Software dient nur zu Informationszwecken und stellt keine Anlageberatung dar. 
Optionshandel ist mit erheblichen Risiken verbunden, insbesondere bei Hebelstrategien.
Konsultieren Sie einen qualifizierten Finanzberater vor Anlageentscheidungen.

## 📝 Geplante Erweiterungen

- [ ] PyQt/PySide Desktop-Version (parallel)
- [ ] Portfolio-Verwaltung
- [x] Backtesting der Optionsstrategie
- [ ] Alerts für wichtige Ereignisse
- [ ] Mehrere Ticker gleichzeitig vergleichen

## 📄 Lizenz

Frei zur persönlichen Verwendung.
