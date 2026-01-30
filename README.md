# 📊 Aktienanalyse für Optionenstrategie

Ein umfassendes Streamlit-basiertes Analyse-Tool für Aktien und ETFs, optimiert für eine Optionenstrategie zur Generierung von Zusatzrente.

## 🎯 Ziel der Strategie

Das Tool unterstützt eine Optionenstrategie mit ca. 7-fachem Hebel:
- **Verkaufte Puts (langlaufend)**: Basisposition
- **Verkaufte Calls (wöchentlich)**: 30-50% des Bestandes, kurzfristige Prämieneinnahme
- **Gekaufte Calls (langlaufend)**: Absicherung der verkauften Calls + Partizipation an Kurssteigerungen
- **Gekaufte Puts (mittelfristig)**: Absicherung der verkauften Puts

## 📋 Features

### 6 Analyse-Reiter:

1. **Holdings**: Zeigt ETF-Bestandteile oder Unternehmensinfos bei Einzelaktien
2. **Kennzahlen**: Alle wichtigen Metriken inkl. 3-Daumen-Regel
3. **Chart 5 Jahre**: Kurs mit Bollinger, SMA200, MACD, RSI
4. **Chart 1 Jahr**: Detaillierte 1-Jahres-Ansicht
5. **Saisonalität**: Wöchentliche saisonale Muster (10 Jahre)
6. **Optionsanalyse**: IV, Strike-Empfehlungen, Optionsketten

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

## 🚀 Installation

```bash
# Repository klonen oder Dateien herunterladen
cd stock_analyzer

# Abhängigkeiten installieren
pip install -r requirements.txt

# Anwendung starten
streamlit run stock_analyzer.py
```

## 📖 Verwendung

1. **Ticker eingeben**: z.B. `KO` (Coca-Cola), `AAPL` (Apple), `SPY` (S&P 500 ETF)
2. **Analysieren klicken**: Lädt alle Daten
3. **Durch die Reiter navigieren**: Verschiedene Analysen erkunden
4. **Zusammenfassung erstellen**: Für späteres Nachschlagen

## 🛠️ Technische Details

- **Datenquelle**: Yahoo Finance (yfinance)
- **Charts**: Plotly (interaktiv)
- **UI**: Streamlit
- **Sprache**: Python 3.8+

## ⚠️ Disclaimer

Diese Software dient nur zu Informationszwecken und stellt keine Anlageberatung dar. 
Optionshandel ist mit erheblichen Risiken verbunden, insbesondere bei Hebelstrategien.
Konsultieren Sie einen qualifizierten Finanzberater vor Anlageentscheidungen.

## 📝 Geplante Erweiterungen

- [ ] PyQt/PySide Desktop-Version (parallel)
- [ ] Portfolio-Verwaltung
- [ ] Backtesting der Optionsstrategie
- [ ] Alerts für wichtige Ereignisse
- [ ] Mehrere Ticker gleichzeitig vergleichen

## 📄 Lizenz

Frei zur persönlichen Verwendung.
