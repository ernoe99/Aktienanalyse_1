# Archiv: frühere Versionen

Dieser Ordner enthält die Entwicklungsstände des Analyse-Tools vor Version 2.9.
Sie werden **nicht** deployt und sind nur zum Nachschlagen bzw. Vergleichen hier.
Die aktive Anwendung ist `../Simple_stock_analyzer_go.py`.

| Datei | Version | Schwerpunkt |
|---|---|---|
| `stock_analyzer.py` | 1.0 | Erste Version: 6 Reiter, 3-Daumen-Regel |
| `stock_analyzer_1.py` | 2.0 | Korrigierte Version |
| `stock_analyzer_2.py`, `_3`, `_4`, `_7` | 2.1 | CHF-/EUR-Währungsumrechnung, Zwischenstände |
| `stock_analyzer_10.py` | 2.6 | Black-Scholes-Bewertung im Backtest |
| `stock_analyzer_12.py` | 2.7 | Echte Strikes aus der Optionskette |
| `stock_analyzer_13.py` | 2.8 | Börsenzeiten-Warnung |
| `Simple_stock_analyzer_go_vorAPIbrake.py` | 2.8 | Stand vor Rate-Limiting-Schutz |
| `stock_analyzer_dualstrategy.py` | 2.9 | Variante: OTM- und ATM/ITM-Strategien mit Call-Verkaufsregeln |
| `stock_analyzer_v3.py` | 3.0 | Variable Strike-Prozente + Strategievergleich (früher Stand) |
| `stock_analyzer_v4.py` | 3.0 | Wie v3, erweitert – identisch mit `../Complex_system_analyzer_go.py` |

Jede Datei ist eine eigenständige Streamlit-App und kann bei Bedarf so gestartet werden:

```bash
streamlit run legacy/stock_analyzer_13.py
```
