"""
Aktienanalyse-Tool für Optionenstrategie zur Rentenergänzung
============================================================
Streamlit-basierte Anwendung zur Analyse von Aktien und ETFs
mit Fokus auf sichere Rendite durch Optionsstrategien.

Autor: Claude
Version: 2.8 - Echte Strikes aus Optionskette + Börsenzeiten-Warnung
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.stats import norm
import pytz
import warnings
warnings.filterwarnings('ignore')

# Streamlit Konfiguration
st.set_page_config(
    page_title="Aktienanalyse für Optionenstrategie",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS für besseres Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin: 5px;
    }
    .metric-card h3 {
        color: #1565c0;
    }
    .metric-card p b {
        color: #1565c0;
    }
    .positive { color: #00a040; }
    .negative { color: #d50000; }
    .neutral { color: #f57c00; }
    .thumb-up { font-size: 24px; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
    }
    .strategy-box {
        background-color: #e3f2fd;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #2196f3;
        color: #1565c0;
    }
    .strategy-comparison {
        display: flex;
        gap: 20px;
    }
</style>
""", unsafe_allow_html=True)


class CurrencyConverter:
    """Klasse für Währungsumrechnung mit historischen Kursen"""
    
    def __init__(self):
        self.rates = {}
        self.historical_rates = {}  # Cache für historische Kurse
        self.base_currency = 'USD'
        self.last_update = None
        
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> float:
        """Holt den aktuellen Wechselkurs"""
        if from_currency == to_currency:
            return 1.0
        
        cache_key = f"{from_currency}_{to_currency}"
        
        # Cache für 1 Stunde
        if cache_key in self.rates and self.last_update:
            if (datetime.now() - self.last_update).seconds < 3600:
                return self.rates[cache_key]
        
        try:
            # yfinance für Wechselkurse nutzen
            ticker = f"{from_currency}{to_currency}=X"
            fx = yf.Ticker(ticker)
            rate = fx.info.get('regularMarketPrice') or fx.info.get('previousClose')
            
            if rate:
                self.rates[cache_key] = rate
                self.last_update = datetime.now()
                return rate
            
            # Fallback: Inverse versuchen
            ticker_inv = f"{to_currency}{from_currency}=X"
            fx_inv = yf.Ticker(ticker_inv)
            rate_inv = fx_inv.info.get('regularMarketPrice') or fx_inv.info.get('previousClose')
            
            if rate_inv:
                rate = 1.0 / rate_inv
                self.rates[cache_key] = rate
                self.last_update = datetime.now()
                return rate
                
        except Exception as e:
            pass
        
        # Fallback-Kurse (Stand: Dezember 2024)
        fallback_rates = {
            'USD_CHF': 0.88,
            'EUR_CHF': 0.93,
            'GBP_CHF': 1.10,
            'CHF_USD': 1.14,
            'CHF_EUR': 1.08,
        }
        
        if cache_key in fallback_rates:
            return fallback_rates[cache_key]
        
        # Über USD als Zwischenwährung
        if from_currency != 'USD' and to_currency != 'USD':
            rate_to_usd = fallback_rates.get(f"{from_currency}_USD", 1.0)
            rate_from_usd = fallback_rates.get(f"USD_{to_currency}", 1.0)
            return rate_to_usd * rate_from_usd
        
        return 1.0
    
    def get_historical_rates(self, from_currency: str, to_currency: str, 
                             period: str = "5y") -> pd.DataFrame:
        """
        Holt historische Wechselkurse für einen Zeitraum.
        
        Args:
            from_currency: Quellwährung (z.B. 'USD')
            to_currency: Zielwährung (z.B. 'CHF')
            period: Zeitraum ('1y', '5y', '10y', etc.)
            
        Returns:
            DataFrame mit Datum als Index und 'Rate' als Spalte
        """
        if from_currency == to_currency:
            return pd.DataFrame()
        
        cache_key = f"{from_currency}_{to_currency}_{period}"
        
        # Cache prüfen
        if cache_key in self.historical_rates:
            return self.historical_rates[cache_key]
        
        try:
            # yfinance für historische Wechselkurse
            ticker = f"{from_currency}{to_currency}=X"
            fx = yf.Ticker(ticker)
            history = fx.history(period=period)
            
            if not history.empty:
                # Nur Close-Kurs verwenden
                rates_df = history[['Close']].copy()
                rates_df.columns = ['Rate']
                
                # Timezone entfernen falls vorhanden
                if rates_df.index.tz is not None:
                    rates_df.index = rates_df.index.tz_localize(None)
                
                self.historical_rates[cache_key] = rates_df
                return rates_df
            
            # Fallback: Inverse versuchen
            ticker_inv = f"{to_currency}{from_currency}=X"
            fx_inv = yf.Ticker(ticker_inv)
            history_inv = fx_inv.history(period=period)
            
            if not history_inv.empty:
                rates_df = history_inv[['Close']].copy()
                rates_df['Rate'] = 1.0 / rates_df['Close']
                rates_df = rates_df[['Rate']]
                
                if rates_df.index.tz is not None:
                    rates_df.index = rates_df.index.tz_localize(None)
                
                self.historical_rates[cache_key] = rates_df
                return rates_df
                
        except Exception as e:
            pass
        
        # Fallback: Leerer DataFrame (wird mit fixem Kurs gefüllt)
        return pd.DataFrame()
    
    def convert_historical(self, df: pd.DataFrame, price_columns: list,
                          from_currency: str, to_currency: str) -> pd.DataFrame:
        """
        Konvertiert historische Preisdaten mit historischen Wechselkursen.
        
        Args:
            df: DataFrame mit Preisdaten (Index = Datum)
            price_columns: Liste der zu konvertierenden Spalten (z.B. ['Open', 'High', 'Low', 'Close'])
            from_currency: Quellwährung
            to_currency: Zielwährung
            
        Returns:
            DataFrame mit konvertierten Preisen
        """
        if from_currency == to_currency:
            return df
        
        df = df.copy()
        
        # Bestimme den Zeitraum basierend auf den Daten
        date_range = (df.index[-1] - df.index[0]).days
        if date_range > 3650:  # > 10 Jahre
            period = "max"
        elif date_range > 1825:  # > 5 Jahre
            period = "10y"
        elif date_range > 365:  # > 1 Jahr
            period = "5y"
        else:
            period = "2y"
        
        # Hole historische Wechselkurse
        fx_rates = self.get_historical_rates(from_currency, to_currency, period)
        
        if fx_rates.empty:
            # Fallback: Fixer Kurs
            fixed_rate = self.get_exchange_rate(from_currency, to_currency)
            for col in price_columns:
                if col in df.columns:
                    df[col] = df[col] * fixed_rate
            df['FX_Rate'] = fixed_rate
            df['FX_Type'] = 'fixed'
            return df
        
        # Timezone des Aktien-DataFrames entfernen falls vorhanden
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Wechselkurse auf Aktiendaten-Index mappen
        # Verwende forward-fill für fehlende Tage (Wochenenden, Feiertage)
        df['FX_Rate'] = np.nan
        
        for date in df.index:
            # Finde den nächsten verfügbaren Wechselkurs
            available_dates = fx_rates.index[fx_rates.index <= date]
            if len(available_dates) > 0:
                closest_date = available_dates[-1]
                df.loc[date, 'FX_Rate'] = fx_rates.loc[closest_date, 'Rate']
        
        # Falls am Anfang Werte fehlen, mit erstem verfügbaren Kurs füllen
        if df['FX_Rate'].isna().any():
            first_valid_rate = df['FX_Rate'].dropna().iloc[0] if not df['FX_Rate'].dropna().empty else self.get_exchange_rate(from_currency, to_currency)
            df['FX_Rate'] = df['FX_Rate'].fillna(first_valid_rate)
        
        # Preise konvertieren
        for col in price_columns:
            if col in df.columns:
                df[col] = df[col] * df['FX_Rate']
        
        df['FX_Type'] = 'historical'
        
        return df
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Konvertiert einen Betrag von einer Währung in eine andere"""
        if amount is None or (isinstance(amount, float) and np.isnan(amount)):
            return amount
        rate = self.get_exchange_rate(from_currency, to_currency)
        return amount * rate


# Globale Instanz des Währungsrechners
currency_converter = CurrencyConverter()


class StockAnalyzer:
    """Hauptklasse für die Aktienanalyse"""
    
    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        self.info = self._get_info()
        self.history_5y = None
        self.history_1y = None
        self.options_data = None
        
    def _get_info(self) -> dict:
        """Holt Basis-Informationen zum Ticker"""
        try:
            return self.stock.info
        except Exception as e:
            st.error(f"Fehler beim Laden der Ticker-Informationen: {e}")
            return {}
    
    def get_history(self, period: str = "5y") -> pd.DataFrame:
        """Holt historische Kursdaten"""
        try:
            return self.stock.history(period=period)
        except Exception as e:
            st.error(f"Fehler beim Laden der Historie: {e}")
            return pd.DataFrame()
    
    def is_etf(self) -> bool:
        """Prüft ob der Ticker ein ETF ist"""
        quote_type = self.info.get('quoteType', '')
        return quote_type == 'ETF'
    
    def get_holdings(self) -> pd.DataFrame:
        """Holt Holdings für ETFs"""
        try:
            if self.is_etf():
                holdings = None
                try:
                    holdings = self.stock.institutional_holders
                except:
                    pass
                
                if holdings is None or holdings.empty:
                    try:
                        holdings = self.stock.major_holders
                    except:
                        pass
                
                if holdings is None or (hasattr(holdings, 'empty') and holdings.empty):
                    top_holdings = self.info.get('holdings', [])
                    if top_holdings:
                        holdings = pd.DataFrame(top_holdings)
                
                return holdings if holdings is not None else pd.DataFrame()
            return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()
    
    def get_key_metrics(self) -> dict:
        """Berechnet alle wichtigen Kennzahlen"""
        metrics = {}
        
        # Basis-Informationen
        metrics['name'] = self.info.get('longName', self.ticker)
        metrics['sector'] = self.info.get('sector', 'N/A')
        metrics['industry'] = self.info.get('industry', 'N/A')
        metrics['currency'] = self.info.get('currency', 'USD')
        metrics['exchange'] = self.info.get('exchange', 'N/A')
        metrics['website'] = self.info.get('website', '')
        
        # Preis-Informationen
        metrics['current_price'] = self.info.get('currentPrice', 
                                   self.info.get('regularMarketPrice', 
                                   self.info.get('previousClose', 0)))
        metrics['previous_close'] = self.info.get('previousClose', 0)
        metrics['open'] = self.info.get('open', 0)
        metrics['day_high'] = self.info.get('dayHigh', 0)
        metrics['day_low'] = self.info.get('dayLow', 0)
        metrics['52w_high'] = self.info.get('fiftyTwoWeekHigh', 0)
        metrics['52w_low'] = self.info.get('fiftyTwoWeekLow', 0)
        
        # Marktdaten
        metrics['market_cap'] = self.info.get('marketCap', 0)
        metrics['enterprise_value'] = self.info.get('enterpriseValue', 0)
        metrics['volume'] = self.info.get('volume', 0)
        metrics['avg_volume'] = self.info.get('averageVolume', 0)
        metrics['avg_volume_10d'] = self.info.get('averageVolume10days', 0)
        
        # Bewertungskennzahlen
        metrics['pe_ratio'] = self.info.get('trailingPE', self.info.get('forwardPE', 0))
        metrics['forward_pe'] = self.info.get('forwardPE', 0)
        metrics['price_to_book'] = self.info.get('priceToBook', 0)
        metrics['price_to_sales'] = self.info.get('priceToSalesTrailing12Months', 0)
        metrics['ev_to_ebitda'] = self.info.get('enterpriseToEbitda', 0)
        
        # Finanzkennzahlen
        metrics['revenue'] = self.info.get('totalRevenue', 0)
        metrics['revenue_growth'] = self.info.get('revenueGrowth', 0)
        metrics['gross_margin'] = self.info.get('grossMargins', 0)
        metrics['operating_margin'] = self.info.get('operatingMargins', 0)
        metrics['profit_margin'] = self.info.get('profitMargins', 0)
        metrics['ebitda'] = self.info.get('ebitda', 0)
        metrics['net_income'] = self.info.get('netIncomeToCommon', 0)
        
        # Free Cash Flow
        metrics['free_cash_flow'] = self.info.get('freeCashflow', 0)
        metrics['operating_cash_flow'] = self.info.get('operatingCashflow', 0)
        
        # FCF Ratio berechnen
        if metrics['market_cap'] and metrics['free_cash_flow']:
            metrics['fcf_yield'] = (metrics['free_cash_flow'] / metrics['market_cap']) * 100
            metrics['price_to_fcf'] = metrics['market_cap'] / metrics['free_cash_flow'] if metrics['free_cash_flow'] > 0 else 0
        else:
            metrics['fcf_yield'] = 0
            metrics['price_to_fcf'] = 0
        
        # Dividenden - KORRIGIERT: Keine doppelte Multiplikation mit 100
        raw_dividend_yield = self.info.get('dividendYield', 0)
        # yfinance gibt dividendYield als Dezimalzahl (0.03 = 3%)
        # Prüfen ob der Wert bereits in Prozent ist (>1) oder als Dezimal (<1)
        if raw_dividend_yield and raw_dividend_yield > 0:
            if raw_dividend_yield > 1:
                # Wert ist bereits in Prozent (z.B. 3.5)
                metrics['dividend_yield'] = raw_dividend_yield
            else:
                # Wert ist Dezimal (z.B. 0.035)
                metrics['dividend_yield'] = raw_dividend_yield * 100
            
            # Sicherheitsprüfung: Dividendenrendite sollte realistisch sein (0-20%)
            if metrics['dividend_yield'] > 20:
                # Wenn größer als 20%, ist wahrscheinlich ein Faktor 100 zu viel
                metrics['dividend_yield'] = metrics['dividend_yield'] / 100
            if metrics['dividend_yield'] > 20:
                # Wenn immer noch größer als 20%, auf 0 setzen (unrealistisch)
                metrics['dividend_yield'] = 0
        else:
            metrics['dividend_yield'] = 0
            
        metrics['dividend_rate'] = self.info.get('dividendRate', 0)
        metrics['payout_ratio'] = self.info.get('payoutRatio', 0)
        metrics['ex_dividend_date'] = self.info.get('exDividendDate', None)
        
        # Volatilität und Beta
        metrics['beta'] = self.info.get('beta', 0)
        
        # Schulden
        metrics['total_debt'] = self.info.get('totalDebt', 0)
        metrics['debt_to_equity'] = self.info.get('debtToEquity', 0)
        metrics['current_ratio'] = self.info.get('currentRatio', 0)
        metrics['quick_ratio'] = self.info.get('quickRatio', 0)
        
        # Earnings
        metrics['earnings_date'] = self.info.get('earningsTimestamp', None)
        
        return metrics
    
    def get_dividend_history_yearly(self) -> pd.DataFrame:
        """
        Holt Dividenden-Historie der letzten 10 Jahre, jahresweise aggregiert.
        Berechnet Rendite mit Jahresanfangskursen.
        """
        try:
            # Hole alle Dividenden
            dividends = self.stock.dividends
            if dividends.empty:
                return pd.DataFrame()
            
            # Hole Kursdaten für 10+ Jahre
            history = self.get_history("11y")
            if history.empty:
                return pd.DataFrame()
            
            # Zeitraum: Letzte 10 Jahre - Timezone-aware machen
            cutoff_year = datetime.now().year - 10
            
            # Dividenden in DataFrame konvertieren
            div_df = dividends.to_frame()
            div_df.columns = ['Dividende']
            
            # Timezone entfernen falls vorhanden (für Vergleichbarkeit)
            if div_df.index.tz is not None:
                div_df.index = div_df.index.tz_localize(None)
            
            div_df.index = pd.to_datetime(div_df.index)
            div_df['Jahr'] = div_df.index.year
            
            # Nach Jahr filtern (statt Datum-Vergleich)
            div_df = div_df[div_df['Jahr'] >= cutoff_year]
            if div_df.empty:
                return pd.DataFrame()
            
            # Jahresweise aggregieren (inkl. Sonderdividenden)
            yearly_div = div_df.groupby('Jahr').agg({
                'Dividende': ['sum', 'count']
            }).reset_index()
            yearly_div.columns = ['Jahr', 'Gesamt_Dividende', 'Anzahl_Zahlungen']
            
            # Jahresanfangskurse holen - Timezone entfernen falls vorhanden
            if history.index.tz is not None:
                history.index = history.index.tz_localize(None)
            history.index = pd.to_datetime(history.index)
            
            jahresanfangskurse = []
            for year in yearly_div['Jahr']:
                year_data = history[history.index.year == year]
                if not year_data.empty:
                    # Erster Handelstag des Jahres
                    first_price = year_data['Close'].iloc[0]
                    jahresanfangskurse.append(first_price)
                else:
                    jahresanfangskurse.append(None)
            
            yearly_div['Jahresanfangskurs'] = jahresanfangskurse
            
            # Dividendenrendite berechnen
            yearly_div['Dividendenrendite_%'] = yearly_div.apply(
                lambda row: (row['Gesamt_Dividende'] / row['Jahresanfangskurs'] * 100) 
                if row['Jahresanfangskurs'] and row['Jahresanfangskurs'] > 0 else 0,
                axis=1
            )
            
            # Einzelne Dividendenzahlungen pro Jahr
            einzelzahlungen = []
            for year in yearly_div['Jahr']:
                year_divs = div_df[div_df['Jahr'] == year]['Dividende'].tolist()
                einzelzahlungen.append(year_divs)
            
            yearly_div['Einzelzahlungen'] = einzelzahlungen
            
            # Sortieren nach Jahr absteigend (neueste zuerst)
            yearly_div = yearly_div.sort_values('Jahr', ascending=False)
            
            return yearly_div
            
        except Exception as e:
            st.error(f"Fehler beim Laden der Dividenden-Historie: {e}")
            return pd.DataFrame()
    
    def get_upcoming_dates(self) -> dict:
        """
        Holt Ex-Dividenden-Datum und Earnings-Termin.
        Prüft ob Daten in der Vergangenheit liegen und schätzt zukünftige Termine.
        """
        dates_info = {
            'ex_dividend_date': None,
            'ex_dividend_date_str': 'Nicht verfügbar',
            'ex_dividend_estimated': False,
            'estimated_dividend': 0,
            'earnings_date': None,
            'earnings_date_str': 'Nicht verfügbar',
            'earnings_estimated': False,
            'data_source': 'yfinance'
        }
        
        now = datetime.now()
        
        # Ex-Dividenden-Datum
        ex_div_timestamp = self.info.get('exDividendDate')
        if ex_div_timestamp:
            try:
                ex_div_date = datetime.fromtimestamp(ex_div_timestamp)
                
                if ex_div_date > now:
                    # Datum liegt in der Zukunft - OK
                    dates_info['ex_dividend_date'] = ex_div_date
                    dates_info['ex_dividend_date_str'] = ex_div_date.strftime('%d.%m.%Y')
                else:
                    # Datum liegt in der Vergangenheit - schätze nächsten Termin
                    dates_info['ex_dividend_estimated'] = True
                    
                    # Hole Dividenden-Historie für Muster-Erkennung
                    dividends = self.stock.dividends
                    if not dividends.empty and len(dividends) >= 2:
                        # Timezone entfernen für Vergleiche
                        div_index = dividends.index
                        if div_index.tz is not None:
                            div_index = div_index.tz_localize(None)
                        
                        # Berechne durchschnittlichen Abstand zwischen Dividenden
                        div_dates = pd.to_datetime(div_index).to_pydatetime()
                        intervals = []
                        for i in range(1, min(len(div_dates), 5)):
                            interval = (div_dates[-i] - div_dates[-i-1]).days
                            intervals.append(interval)
                        
                        avg_interval = np.mean(intervals) if intervals else 90
                        
                        # Schätze nächsten Termin
                        last_div_date = div_dates[-1]
                        # Stelle sicher, dass last_div_date timezone-naive ist
                        if hasattr(last_div_date, 'tzinfo') and last_div_date.tzinfo is not None:
                            last_div_date = last_div_date.replace(tzinfo=None)
                        
                        estimated_next = last_div_date + timedelta(days=avg_interval)
                        
                        # Falls geschätzter Termin auch in der Vergangenheit liegt
                        while estimated_next < now:
                            estimated_next += timedelta(days=avg_interval)
                        
                        dates_info['ex_dividend_date'] = estimated_next
                        dates_info['ex_dividend_date_str'] = f"~{estimated_next.strftime('%d.%m.%Y')} (geschätzt)"
                        
                        # Schätze Dividendenhöhe (letzte Dividende)
                        dates_info['estimated_dividend'] = dividends.iloc[-1]
                        
            except Exception as e:
                pass
        
        # Earnings-Datum
        try:
            # Versuche über Calendar
            calendar = self.stock.calendar
            if calendar is not None and not calendar.empty:
                if 'Earnings Date' in calendar.index:
                    earnings_dates = calendar.loc['Earnings Date']
                    if isinstance(earnings_dates, pd.Series):
                        earnings_date = pd.to_datetime(earnings_dates.iloc[0])
                    else:
                        earnings_date = pd.to_datetime(earnings_dates)
                    
                    # Timezone entfernen für Vergleich
                    if hasattr(earnings_date, 'tz') and earnings_date.tz is not None:
                        earnings_date = earnings_date.tz_localize(None)
                    
                    # In naive datetime konvertieren
                    earnings_date_naive = earnings_date.to_pydatetime() if hasattr(earnings_date, 'to_pydatetime') else earnings_date
                    if hasattr(earnings_date_naive, 'tzinfo') and earnings_date_naive.tzinfo is not None:
                        earnings_date_naive = earnings_date_naive.replace(tzinfo=None)
                    
                    if earnings_date_naive > now:
                        dates_info['earnings_date'] = earnings_date_naive
                        dates_info['earnings_date_str'] = earnings_date_naive.strftime('%d.%m.%Y')
        except:
            pass
        
        # Falls Earnings-Datum nicht gefunden oder in Vergangenheit
        if dates_info['earnings_date'] is None:
            earnings_timestamp = self.info.get('earningsTimestamp') or self.info.get('mostRecentQuarter')
            if earnings_timestamp:
                try:
                    earnings_date = datetime.fromtimestamp(earnings_timestamp)
                    
                    if earnings_date > now:
                        dates_info['earnings_date'] = earnings_date
                        dates_info['earnings_date_str'] = earnings_date.strftime('%d.%m.%Y')
                    else:
                        # Schätze nächsten Quartalstermin (ca. 90 Tage)
                        dates_info['earnings_estimated'] = True
                        estimated_earnings = earnings_date + timedelta(days=90)
                        while estimated_earnings < now:
                            estimated_earnings += timedelta(days=90)
                        
                        dates_info['earnings_date'] = estimated_earnings
                        dates_info['earnings_date_str'] = f"~{estimated_earnings.strftime('%d.%m.%Y')} (geschätzt)"
                except:
                    pass
        
        return dates_info
    
    def calculate_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Berechnet gleitende Durchschnitte"""
        df = df.copy()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        return df
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """Berechnet Bollinger Bänder"""
        df = df.copy()
        df['BB_Middle'] = df['Close'].rolling(window=window).mean()
        df['BB_Std'] = df['Close'].rolling(window=window).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * num_std)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * num_std)
        return df
    
    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Berechnet MACD"""
        df = df.copy()
        df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        return df
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Berechnet RSI"""
        df = df.copy()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        return df
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Berechnet Average True Range"""
        df = df.copy()
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=period).mean()
        return df
    
    def calculate_historical_volatility(self, df: pd.DataFrame, window: int = 30) -> float:
        """Berechnet historische Volatilität"""
        returns = df['Close'].pct_change().dropna()
        volatility = returns.rolling(window=window).std() * np.sqrt(252) * 100
        return volatility.iloc[-1] if len(volatility) > 0 else 0
    
    def calculate_three_thumbs_rule(self) -> dict:
        """
        Berechnet die 3-Daumen-Regel:
        1. Über 200 Tage Linie = +1 Daumen
        2. Year to date positiv = +1 Daumen
        3. Ungerades Jahr: Erste 5 Tage positiv = +1 Daumen
           Gerades Jahr: 70% erste 5 Tage + 30% gerades Jahr
        """
        result = {
            'thumb1': {'value': False, 'description': 'Über 200-Tage-Linie'},
            'thumb2': {'value': False, 'description': 'Year-to-Date positiv'},
            'thumb3': {'value': False, 'description': 'Jahresregel'},
            'total_thumbs': 0,
            'details': {}
        }
        
        try:
            history = self.get_history("2y")
            if history.empty:
                return result
            
            current_price = history['Close'].iloc[-1]
            
            # Thumb 1: Über 200-Tage-Linie
            if len(history) >= 200:
                sma_200 = history['Close'].rolling(window=200).mean().iloc[-1]
                result['thumb1']['value'] = current_price > sma_200
                result['details']['sma_200'] = sma_200
                result['details']['price_vs_sma200'] = ((current_price / sma_200) - 1) * 100
            
            # Thumb 2: Year-to-Date positiv
            current_year = datetime.now().year
            ytd_data = history[history.index.year == current_year]
            if not ytd_data.empty:
                first_price_ytd = ytd_data['Close'].iloc[0]
                ytd_return = ((current_price / first_price_ytd) - 1) * 100
                result['thumb2']['value'] = ytd_return > 0
                result['details']['ytd_return'] = ytd_return
            
            # Thumb 3: Jahresregel
            is_odd_year = current_year % 2 != 0
            current_month = datetime.now().month
            
            # Immer die ersten 5 Handelstage berechnen
            first_5_days = ytd_data.head(5)
            if len(first_5_days) >= 2:
                first_5_days_return = ((first_5_days['Close'].iloc[-1] / first_5_days['Close'].iloc[0]) - 1) * 100
                result['details']['first_5_days_return'] = first_5_days_return
            
            result['details']['current_month'] = current_month
            
            # Für die Regel: Januar nutzt erste 5 Tage, Feb-Dez nutzt gesamten Januar
            if current_month == 1:
                # Januar: Nutze erste 5 Tage für Bewertung
                if 'first_5_days_return' in result['details']:
                    first_5_positive = result['details']['first_5_days_return'] > 0
                    evaluation_return = result['details']['first_5_days_return']
            else:
                # Februar bis Dezember: Nutze gesamten Januar für Bewertung
                january_data = history[(history.index.year == current_year) & (history.index.month == 1)]
                if not january_data.empty:
                    first_jan_close = january_data['Close'].iloc[0]
                    last_jan_close = january_data['Close'].iloc[-1]
                    january_return = ((last_jan_close / first_jan_close) - 1) * 100
                    first_5_positive = january_return > 0
                    result['details']['january_return'] = january_return
                    evaluation_return = january_return
                else:
                    # Fallback auf erste 5 Tage
                    if 'first_5_days_return' in result['details']:
                        first_5_positive = result['details']['first_5_days_return'] > 0
                        evaluation_return = result['details']['first_5_days_return']
                
            if 'first_5_days_return' in result['details'] or 'january_return' in result['details']:
                if is_odd_year:
                    result['thumb3']['value'] = first_5_positive
                    result['thumb3']['description'] = f'Ungerades Jahr: Erste 5 Tage {"positiv" if first_5_positive else "negativ"}'
                else:
                    score = 0.7 * (1 if first_5_positive else 0) + 0.3 * 1
                    result['thumb3']['value'] = score >= 0.5
                    result['thumb3']['description'] = f'Gerades Jahr: Score {score:.1%}'
            
            result['details']['is_odd_year'] = is_odd_year
            
            result['total_thumbs'] = sum([
                result['thumb1']['value'],
                result['thumb2']['value'],
                result['thumb3']['value']
            ])
            
        except Exception as e:
            st.error(f"Fehler bei 3-Daumen-Berechnung: {e}")
        
        return result
    
    def get_options_info(self) -> dict:
        """Holt Optionsinformationen mit erweiterter Kategorisierung"""
        options_info = {
            'expiration_dates': [],
            'weekly': [],           # ≤14 Tage
            'monthly': [],          # 15-45 Tage
            'quarterly': [],        # 46-180 Tage (3-6 Monate)
            'semi_annual': [],      # 181-365 Tage (6-12 Monate)
            'annual': [],           # 366-730 Tage (12-24 Monate)
            'leaps': [],            # >730 Tage (>24 Monate)
            'chains': {}
        }
        
        try:
            expirations = self.stock.options
            if expirations:
                options_info['expiration_dates'] = list(expirations)
                
                now = datetime.now()
                
                for exp in expirations:
                    exp_date = datetime.strptime(exp, '%Y-%m-%d')
                    days_to_exp = (exp_date - now).days
                    
                    if days_to_exp <= 14:
                        options_info['weekly'].append(exp)
                    elif days_to_exp <= 45:
                        options_info['monthly'].append(exp)
                    elif days_to_exp <= 180:
                        options_info['quarterly'].append(exp)
                    elif days_to_exp <= 365:
                        options_info['semi_annual'].append(exp)
                    elif days_to_exp <= 730:
                        options_info['annual'].append(exp)
                    else:
                        options_info['leaps'].append(exp)
                
                # Hole mehr Optionsketten für Strategieempfehlungen
                # Wöchentlich, 3-6 Monate, 6-12 Monate, 12-24 Monate
                target_expirations = []
                
                if options_info['weekly']:
                    target_expirations.append(options_info['weekly'][0])
                if options_info['monthly']:
                    target_expirations.append(options_info['monthly'][0])
                if options_info['quarterly']:
                    target_expirations.extend(options_info['quarterly'][:2])
                if options_info['semi_annual']:
                    target_expirations.extend(options_info['semi_annual'][:2])
                if options_info['annual']:
                    target_expirations.extend(options_info['annual'][:2])
                if options_info['leaps']:
                    target_expirations.append(options_info['leaps'][0])
                
                for exp in target_expirations:
                    try:
                        chain = self.stock.option_chain(exp)
                        options_info['chains'][exp] = {
                            'calls': chain.calls,
                            'puts': chain.puts
                        }
                    except:
                        pass
                            
        except Exception as e:
            pass
        
        return options_info
    
    def calculate_implied_volatility(self) -> dict:
        """
        Berechnet durchschnittliche implizite Volatilität.
        KORRIGIERT: Nur ATM-Optionen (±10% vom Kurs) berücksichtigen für realistischere Werte.
        """
        iv_info = {
            'avg_call_iv': 0,
            'avg_put_iv': 0,
            'atm_iv': 0,
            'iv_percentile': 0
        }
        
        try:
            options = self.get_options_info()
            if options['chains']:
                first_exp = list(options['chains'].keys())[0]
                chain = options['chains'][first_exp]
                
                current_price = self.info.get('currentPrice', 
                               self.info.get('regularMarketPrice', 0))
                
                if current_price > 0:
                    # Filtern auf ATM-Optionen (±10% vom aktuellen Kurs)
                    lower_bound = current_price * 0.90
                    upper_bound = current_price * 1.10
                    
                    # Calls filtern
                    calls = chain['calls']
                    atm_calls = calls[(calls['strike'] >= lower_bound) & (calls['strike'] <= upper_bound)]
                    
                    if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns:
                        # IV ist bereits Dezimal in yfinance (0.25 = 25%)
                        valid_iv = atm_calls['impliedVolatility'].dropna()
                        valid_iv = valid_iv[(valid_iv > 0) & (valid_iv < 5)]  # Filter unrealistische Werte
                        if len(valid_iv) > 0:
                            iv_info['avg_call_iv'] = valid_iv.mean() * 100
                    
                    # Puts filtern
                    puts = chain['puts']
                    atm_puts = puts[(puts['strike'] >= lower_bound) & (puts['strike'] <= upper_bound)]
                    
                    if not atm_puts.empty and 'impliedVolatility' in atm_puts.columns:
                        valid_iv = atm_puts['impliedVolatility'].dropna()
                        valid_iv = valid_iv[(valid_iv > 0) & (valid_iv < 5)]
                        if len(valid_iv) > 0:
                            iv_info['avg_put_iv'] = valid_iv.mean() * 100
                    
                    # ATM IV (nächster Strike zum aktuellen Preis)
                    atm_strike_calls = calls.iloc[(calls['strike'] - current_price).abs().argsort()[:1]]
                    if not atm_strike_calls.empty and 'impliedVolatility' in atm_strike_calls.columns:
                        atm_iv_val = atm_strike_calls['impliedVolatility'].values[0]
                        if 0 < atm_iv_val < 5:  # Nur wenn realistisch
                            iv_info['atm_iv'] = atm_iv_val * 100
                        
        except Exception as e:
            pass
        
        return iv_info
    
    def get_strategy_options(self) -> dict:
        """
        Holt Optionsdaten für die Strategiekombinationen:
        1. Langlaufender Call Kauf (6-12 Monate)
        2. Langlaufender Put Verkauf (12-24 Monate)
        3. Sicherungs-Put Kauf (3-6 Monate)
        4. Kurzlaufender Call Verkauf (wöchentlich)
        """
        strategy_options = {
            'long_call_buy': {'expiration': None, 'options': None, 'days': 0},
            'long_put_sell': {'expiration': None, 'options': None, 'days': 0},
            'hedge_put_buy': {'expiration': None, 'options': None, 'days': 0},
            'short_call_sell': {'expiration': None, 'options': None, 'days': 0}
        }
        
        options_info = self.get_options_info()
        now = datetime.now()
        
        # 1. Langlaufender Call Kauf (6-12 Monate)
        target_exps = options_info['semi_annual']
        if target_exps and target_exps[0] in options_info['chains']:
            exp = target_exps[0]
            days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
            strategy_options['long_call_buy'] = {
                'expiration': exp,
                'options': options_info['chains'][exp]['calls'],
                'days': days
            }
        
        # 2. Langlaufender Put Verkauf (12-24 Monate)
        target_exps = options_info['annual']
        if target_exps and target_exps[0] in options_info['chains']:
            exp = target_exps[0]
            days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
            strategy_options['long_put_sell'] = {
                'expiration': exp,
                'options': options_info['chains'][exp]['puts'],
                'days': days
            }
        elif options_info['leaps'] and options_info['leaps'][0] in options_info['chains']:
            exp = options_info['leaps'][0]
            days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
            strategy_options['long_put_sell'] = {
                'expiration': exp,
                'options': options_info['chains'][exp]['puts'],
                'days': days
            }
        
        # 3. Sicherungs-Put Kauf (3-6 Monate)
        target_exps = options_info['quarterly']
        if target_exps and target_exps[0] in options_info['chains']:
            exp = target_exps[0]
            days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
            strategy_options['hedge_put_buy'] = {
                'expiration': exp,
                'options': options_info['chains'][exp]['puts'],
                'days': days
            }
        
        # 4. Kurzlaufender Call Verkauf (wöchentlich)
        target_exps = options_info['weekly'] or options_info['monthly']
        if target_exps and target_exps[0] in options_info['chains']:
            exp = target_exps[0]
            days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
            strategy_options['short_call_sell'] = {
                'expiration': exp,
                'options': options_info['chains'][exp]['calls'],
                'days': days
            }
        
        return strategy_options
    
    def get_seasonal_data(self) -> pd.DataFrame:
        """Berechnet saisonale Muster auf wöchentlicher Basis"""
        try:
            history = self.get_history("10y")
            if history.empty:
                return pd.DataFrame()
            
            history = history.copy()
            history['Week'] = history.index.isocalendar().week
            history['Year'] = history.index.year
            history['Return'] = history['Close'].pct_change()
            
            weekly_returns = history.groupby(['Year', 'Week'])['Return'].sum().reset_index()
            
            seasonal = weekly_returns.groupby('Week')['Return'].agg(['mean', 'std', 'count']).reset_index()
            seasonal.columns = ['Week', 'Avg_Return', 'Std_Return', 'Count']
            seasonal['Avg_Return_Pct'] = seasonal['Avg_Return'] * 100
            
            positive_weeks = weekly_returns.groupby('Week').apply(
                lambda x: (x['Return'] > 0).sum() / len(x) * 100
            ).reset_index()
            positive_weeks.columns = ['Week', 'Positive_Pct']
            
            seasonal = seasonal.merge(positive_weeks, on='Week')
            
            return seasonal
            
        except Exception as e:
            return pd.DataFrame()


def format_number(value, format_type='number', from_currency='USD', to_currency='USD', symbol=None):
    """
    Formatiert Zahlen für die Anzeige mit optionaler Währungsumrechnung.
    
    Args:
        value: Der zu formatierende Wert
        format_type: 'number', 'currency', 'percent', 'ratio'
        from_currency: Ursprungswährung (z.B. 'USD')
        to_currency: Zielwährung (z.B. 'CHF')
        symbol: Währungssymbol überschreiben (optional)
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 'N/A'
    
    # Währungssymbole
    currency_symbols = {
        'USD': '$',
        'CHF': 'CHF ',
        'EUR': '€',
        'GBP': '£',
    }
    
    # Währungsumrechnung wenn nötig
    if format_type == 'currency' and from_currency != to_currency:
        value = currency_converter.convert(value, from_currency, to_currency)
    
    # Symbol bestimmen
    if symbol is None:
        symbol = currency_symbols.get(to_currency, '$')
    
    if format_type == 'currency':
        if abs(value) >= 1e12:
            return f"{symbol}{value/1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"{symbol}{value/1e9:.2f}B"
        elif abs(value) >= 1e6:
            return f"{symbol}{value/1e6:.2f}M"
        else:
            return f"{symbol}{value:,.2f}"
    elif format_type == 'percent':
        return f"{value:.2f}%"
    elif format_type == 'ratio':
        return f"{value:.2f}"
    else:
        if abs(value) >= 1e9:
            return f"{value/1e9:.2f}B"
        elif abs(value) >= 1e6:
            return f"{value/1e6:.2f}M"
        else:
            return f"{value:,.2f}"


def format_price(value, from_currency='USD', to_currency='USD'):
    """Kurzform für Preisformatierung mit Währungsumrechnung"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 'N/A'
    
    converted = currency_converter.convert(value, from_currency, to_currency)
    symbol = 'CHF ' if to_currency == 'CHF' else '$'
    return f"{symbol}{converted:,.2f}"


def create_price_chart(df: pd.DataFrame, title: str, show_candles: bool = True,
                       fx_rate: float = 1.0, currency_symbol: str = '$',
                       source_currency: str = 'USD', target_currency: str = 'CHF') -> go.Figure:
    """
    Erstellt den Preischart mit allen Indikatoren, historischer Währungsumrechnung
    und Wechselkursverlauf.
    
    Args:
        df: DataFrame mit OHLCV-Daten
        title: Chart-Titel
        show_candles: True für Kerzen, False für Linie
        fx_rate: Fallback-Wechselkurs (wird durch historische Kurse ersetzt wenn verfügbar)
        currency_symbol: Währungssymbol für Zielwährung
        source_currency: Quellwährung (z.B. 'USD')
        target_currency: Zielwährung (z.B. 'CHF')
    """
    
    # Kopie erstellen
    df = df.copy()
    
    # Timezone entfernen falls vorhanden
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Original-Preise speichern (für sekundäre Y-Achse)
    df['Close_Original'] = df['Close'].copy()
    df['Open_Original'] = df['Open'].copy()
    df['High_Original'] = df['High'].copy()
    df['Low_Original'] = df['Low'].copy()
    
    # Prüfen ob Währungsumrechnung nötig ist
    show_dual_currency = (source_currency != target_currency)
    
    if show_dual_currency:
        # Historische Wechselkurse holen und anwenden
        df = currency_converter.convert_historical(
            df, 
            ['Open', 'High', 'Low', 'Close'],
            source_currency, 
            target_currency
        )
        
        # Prüfen ob historische Kurse verwendet wurden
        uses_historical_fx = df.get('FX_Type', pd.Series(['fixed'])).iloc[0] == 'historical'
    else:
        df['FX_Rate'] = 1.0
        uses_historical_fx = False
    
    # Indikatoren auf umgerechneten Preisen berechnen
    analyzer_temp = StockAnalyzer.__new__(StockAnalyzer)
    df = analyzer_temp.calculate_moving_averages(df)
    df = analyzer_temp.calculate_bollinger_bands(df)
    df = analyzer_temp.calculate_macd(df)
    df = analyzer_temp.calculate_rsi(df)
    
    # 5 Subplots: Preis, FX-Kurs, Volumen, MACD, RSI
    if show_dual_currency:
        fig = make_subplots(
            rows=5, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.40, 0.12, 0.12, 0.18, 0.18],
            subplot_titles=(title, f'{source_currency}/{target_currency} Wechselkurs', 
                          'Volumen', 'MACD', 'RSI'),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}],
                   [{"secondary_y": False}], [{"secondary_y": False}], 
                   [{"secondary_y": False}]]
        )
    else:
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.5, 0.15, 0.15, 0.2],
            subplot_titles=(title, 'Volumen', 'MACD', 'RSI'),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}],
                   [{"secondary_y": False}], [{"secondary_y": False}]]
        )
    
    # Preischart
    if show_candles:
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name=f'Kurs ({target_currency})',
                increasing_line_color='#00c853',
                decreasing_line_color='#ff1744'
            ),
            row=1, col=1, secondary_y=False
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['Close'],
                mode='lines',
                name=f'Kurs ({target_currency})',
                line=dict(color='#2196f3', width=2)
            ),
            row=1, col=1, secondary_y=False
        )
    
    # Sekundäre Y-Achse mit Originalwährung (USD)
    if show_dual_currency:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['Close_Original'],
                mode='lines',
                name=f'Kurs ({source_currency})',
                line=dict(color='rgba(100,100,100,0.5)', width=1, dash='dot'),
                hovertemplate=f'{source_currency} %{{y:.2f}}<extra></extra>'
            ),
            row=1, col=1, secondary_y=True
        )
    
    # Bollinger Bänder
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['BB_Upper'],
            mode='lines', name='BB Upper',
            line=dict(color='rgba(128,128,128,0.5)', width=1),
            showlegend=False
        ),
        row=1, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['BB_Lower'],
            mode='lines', name='BB Lower',
            line=dict(color='rgba(128,128,128,0.5)', width=1),
            fill='tonexty', fillcolor='rgba(128,128,128,0.1)',
            showlegend=False
        ),
        row=1, col=1, secondary_y=False
    )
    
    # SMAs
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA_200'],
            mode='lines', name='SMA 200',
            line=dict(color='#ff9800', width=2)
        ),
        row=1, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA_50'],
            mode='lines', name='SMA 50',
            line=dict(color='#9c27b0', width=1.5)
        ),
        row=1, col=1, secondary_y=False
    )
    
    # Wechselkurs-Chart (nur wenn Dual-Currency)
    if show_dual_currency:
        # FX-Rate Chart
        fx_color = '#e91e63'  # Pink für Wechselkurs
        fig.add_trace(
            go.Scatter(
                x=df.index, 
                y=df['FX_Rate'],
                mode='lines',
                name=f'{source_currency}/{target_currency}',
                line=dict(color=fx_color, width=1.5),
                fill='tozeroy',
                fillcolor='rgba(233,30,99,0.1)',
                hovertemplate=f'%{{x}}<br>{source_currency}/{target_currency}: %{{y:.4f}}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Durchschnittlicher FX-Kurs als Referenzlinie
        avg_fx = df['FX_Rate'].mean()
        fig.add_hline(y=avg_fx, line_dash="dash", line_color="gray", 
                      annotation_text=f"Ø {avg_fx:.4f}", row=2, col=1)
        
        volume_row = 3
        macd_row = 4
        rsi_row = 5
    else:
        volume_row = 2
        macd_row = 3
        rsi_row = 4
    
    # Volumen
    colors = ['#00c853' if df['Close'].iloc[i] >= df['Open'].iloc[i] 
              else '#ff1744' for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], name='Volumen', marker_color=colors,
               showlegend=False),
        row=volume_row, col=1
    )
    
    # MACD
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD',
                   line=dict(color='#2196f3', width=1.5), showlegend=False),
        row=macd_row, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal',
                   line=dict(color='#ff9800', width=1.5), showlegend=False),
        row=macd_row, col=1
    )
    colors_macd = ['#00c853' if val >= 0 else '#ff1744' for val in df['MACD_Histogram']]
    fig.add_trace(
        go.Bar(x=df.index, y=df['MACD_Histogram'], name='Histogram', marker_color=colors_macd,
               showlegend=False),
        row=macd_row, col=1
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI',
                   line=dict(color='#9c27b0', width=1.5), showlegend=False),
        row=rsi_row, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=rsi_row, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=rsi_row, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.1)", 
                  line_width=0, row=rsi_row, col=1)
    
    # Layout
    chart_height = 1050 if show_dual_currency else 900
    fig.update_layout(
        height=chart_height,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        template='plotly_white'
    )
    
    # Y-Achsen Beschriftung
    target_label = target_currency if target_currency else currency_symbol.strip()
    fig.update_yaxes(title_text=f"Preis ({target_label})", row=1, col=1, secondary_y=False,
                     tickformat=".2f")
    
    if show_dual_currency:
        fig.update_yaxes(title_text=f"Preis ({source_currency})", row=1, col=1, secondary_y=True,
                         tickformat=".2f", showgrid=False)
        fig.update_yaxes(title_text=f"{source_currency}/{target_currency}", row=2, col=1,
                         tickformat=".4f")
    
    fig.update_yaxes(title_text="Vol", row=volume_row, col=1)
    fig.update_yaxes(title_text="MACD", row=macd_row, col=1)
    fig.update_yaxes(title_text="RSI", row=rsi_row, col=1)
    
    return fig


def create_seasonal_chart(seasonal_data: pd.DataFrame, ticker: str) -> go.Figure:
    """Erstellt den saisonalen Chart"""
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(
            f'Durchschnittliche wöchentliche Rendite - {ticker}',
            'Anteil positiver Wochen (%)'
        )
    )
    
    colors = ['#00c853' if r >= 0 else '#ff1744' for r in seasonal_data['Avg_Return_Pct']]
    
    fig.add_trace(
        go.Bar(
            x=seasonal_data['Week'],
            y=seasonal_data['Avg_Return_Pct'],
            name='Avg Return',
            marker_color=colors,
            text=[f"{r:.2f}%" for r in seasonal_data['Avg_Return_Pct']],
            textposition='outside'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=seasonal_data['Week'],
            y=seasonal_data['Positive_Pct'],
            name='Positive %',
            marker_color='#2196f3',
            text=[f"{p:.0f}%" for p in seasonal_data['Positive_Pct']],
            textposition='outside'
        ),
        row=2, col=1
    )
    
    fig.add_hline(y=50, line_dash="dash", line_color="gray", row=2, col=1)
    
    fig.update_layout(
        height=700,
        showlegend=False,
        template='plotly_white'
    )
    
    fig.update_xaxes(title_text="Kalenderwoche", row=2, col=1)
    fig.update_yaxes(title_text="Rendite (%)", row=1, col=1)
    fig.update_yaxes(title_text="Positive Wochen (%)", row=2, col=1)
    
    return fig


def display_three_thumbs(thumbs_result: dict):
    """Zeigt die 3-Daumen-Regel grafisch an"""
    
    st.subheader("📊 3-Daumen-Regel")
    
    cols = st.columns(4)
    
    with cols[0]:
        thumb1_emoji = "👍" if thumbs_result['thumb1']['value'] else "👎"
        thumb1_color = "positive" if thumbs_result['thumb1']['value'] else "negative"
        price_vs_sma = thumbs_result['details'].get('price_vs_sma200', 0)
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb1_emoji} Daumen 1</h3>
            <p><b>{thumbs_result['thumb1']['description']}</b></p>
            <p><b>Abstand zu SMA200:</b> <span class="{thumb1_color}">{price_vs_sma:+.2f}%</span></p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        thumb2_emoji = "👍" if thumbs_result['thumb2']['value'] else "👎"
        thumb2_color = "positive" if thumbs_result['thumb2']['value'] else "negative"
        ytd_return = thumbs_result['details'].get('ytd_return', 0)
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb2_emoji} Daumen 2</h3>
            <p><b>{thumbs_result['thumb2']['description']}</b></p>
            <p><b>YTD:</b> <span class="{thumb2_color}">{ytd_return:+.2f}%</span></p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        thumb3_emoji = "👍" if thumbs_result['thumb3']['value'] else "👎"
        thumb3_color = "positive" if thumbs_result['thumb3']['value'] else "negative"
        current_month = thumbs_result['details'].get('current_month', 1)
        first_5_return = thumbs_result['details'].get('first_5_days_return', 0)
        
        # Von Februar bis Dezember: Zusätzlich Januar Abschluss anzeigen
        january_html = ""
        if current_month > 1 and 'january_return' in thumbs_result['details']:
            january_return = thumbs_result['details']['january_return']
            january_color = "positive" if january_return > 0 else "negative"
            january_html = f'<p><b>Januar Abschluss:</b> <span class="{january_color}">{january_return:+.2f}%</span></p>'
        
        # Komplettes HTML auf einmal bauen
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb3_emoji} Daumen 3</h3>
            <p><b>{thumbs_result['thumb3']['description']}</b></p>
            <p><b>Erste 5 Tage:</b> <span class="{thumb3_color}">{first_5_return:+.2f}%</span></p>
            {january_html}
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        total = thumbs_result['total_thumbs']
        year_type = "Ungerade" if thumbs_result['details'].get('is_odd_year', True) else "Gerade"
        
        if total == 3:
            rating = "🟢 SEHR GUT"
            rating_color = "positive"
        elif total == 2:
            rating = "🟡 GUT"
            rating_color = "neutral"
        else:
            rating = "🔴 VORSICHT"
            rating_color = "negative"
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>Gesamt: {total}/3</h3>
            <p><b>Jahr: {year_type}</b></p>
            <p class="{rating_color}" style="font-size: 20px;"><b>{rating}</b></p>
            <p>{"👍" * total}{"👎" * (3-total)}</p>
        </div>
        """, unsafe_allow_html=True)


def display_dividend_history(analyzer: StockAnalyzer, source_currency: str = 'USD', 
                            target_currency: str = 'CHF', curr_symbol: str = 'CHF '):
    """Zeigt die Dividenden-Historie der letzten 10 Jahre mit Währungsumrechnung"""
    
    st.subheader(f"💰 Dividenden-Historie (10 Jahre) in {target_currency}")
    
    div_history = analyzer.get_dividend_history_yearly()
    
    if div_history.empty:
        st.info("Keine Dividenden-Daten verfügbar")
        return
    
    # Währungsumrechnung
    rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    
    # Tabelle mit allen Daten
    display_df = div_history[['Jahr', 'Gesamt_Dividende', 'Anzahl_Zahlungen', 
                              'Jahresanfangskurs', 'Dividendenrendite_%']].copy()
    
    display_df.columns = ['Jahr', f'Gesamt-Dividende ({target_currency})', 'Zahlungen', 
                          f'Jahresanfangskurs ({target_currency})', 'Rendite (%)']
    
    # Formatierung mit Währungsumrechnung
    display_df[f'Gesamt-Dividende ({target_currency})'] = display_df[f'Gesamt-Dividende ({target_currency})'].apply(
        lambda x: f"{curr_symbol}{x * rate:.4f}"
    )
    display_df[f'Jahresanfangskurs ({target_currency})'] = display_df[f'Jahresanfangskurs ({target_currency})'].apply(
        lambda x: f"{curr_symbol}{x * rate:.2f}" if x else "N/A"
    )
    display_df['Rendite (%)'] = display_df['Rendite (%)'].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Einzelzahlungen aufklappbar
    with st.expander("📋 Einzelne Dividendenzahlungen pro Jahr"):
        for _, row in div_history.iterrows():
            year = row['Jahr']
            payments = row['Einzelzahlungen']
            if payments:
                payments_str = ", ".join([f"{curr_symbol}{p * rate:.4f}" for p in payments])
                st.write(f"**{year}:** {payments_str}")
    
    # Durchschnitt berechnen
    avg_yield = div_history['Dividendenrendite_%'].mean()
    st.metric("Ø Dividendenrendite (10 Jahre)", f"{avg_yield:.2f}%")


def display_options_analysis(analyzer: StockAnalyzer, metrics: dict, 
                            source_currency: str = 'USD', target_currency: str = 'CHF',
                            curr_symbol: str = 'CHF '):
    """Zeigt die Optionsanalyse mit Strategiekombinationen an"""
    
    st.subheader(f"📋 Verfügbare Optionstermine (Preise in {target_currency})")
    
    options_info = analyzer.get_options_info()
    
    if not options_info['expiration_dates']:
        st.warning("Keine Optionsdaten verfügbar für diesen Ticker.")
        return
    
    # Termine nach Kategorien
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📅 Kurzfristig**")
        st.write("*Wöchentlich (≤14 Tage):*")
        if options_info['weekly']:
            for exp in options_info['weekly'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
        
        st.write("*Monatlich (15-45 Tage):*")
        if options_info['monthly']:
            for exp in options_info['monthly'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
    
    with col2:
        st.markdown("**📆 Mittelfristig**")
        st.write("*3-6 Monate:*")
        if options_info['quarterly']:
            for exp in options_info['quarterly'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
        
        st.write("*6-12 Monate:*")
        if options_info['semi_annual']:
            for exp in options_info['semi_annual'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
    
    with col3:
        st.markdown("**📊 Langfristig**")
        st.write("*12-24 Monate:*")
        if options_info['annual']:
            for exp in options_info['annual'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
        
        st.write("*LEAPS (>24 Monate):*")
        if options_info['leaps']:
            for exp in options_info['leaps'][:3]:
                st.write(f"• {exp}")
        else:
            st.write("Keine")
    
    st.divider()
    
    # Volatilitätsanalyse - KORRIGIERT
    st.subheader("📈 Volatilitätsanalyse")
    
    iv_info = analyzer.calculate_implied_volatility()
    
    history = analyzer.get_history("1y")
    hist_vol = analyzer.calculate_historical_volatility(history) if not history.empty else 0
    
    vol_cols = st.columns(4)
    
    with vol_cols[0]:
        st.metric("ATM Implied Volatility", f"{iv_info['atm_iv']:.1f}%",
                 help="IV der Option am nächsten zum aktuellen Kurs")
    
    with vol_cols[1]:
        st.metric("Historische Volatilität (30d)", f"{hist_vol:.1f}%",
                 help="Realisierte Volatilität der letzten 30 Tage")
    
    with vol_cols[2]:
        st.metric("Ø ATM Call IV", f"{iv_info['avg_call_iv']:.1f}%",
                 help="Durchschnitt nur für Optionen ±10% vom Kurs")
    
    with vol_cols[3]:
        st.metric("Ø ATM Put IV", f"{iv_info['avg_put_iv']:.1f}%",
                 help="Durchschnitt nur für Optionen ±10% vom Kurs")
    
    # IV vs HV Vergleich
    if iv_info['atm_iv'] > 0 and hist_vol > 0:
        iv_premium = ((iv_info['atm_iv'] / hist_vol) - 1) * 100
        if iv_premium > 20:
            st.success(f"📈 IV Premium: {iv_premium:.1f}% - Gute Bedingungen für Optionsverkauf!")
        elif iv_premium < -10:
            st.warning(f"📉 IV Discount: {iv_premium:.1f}% - Ungünstig für Optionsverkauf")
        else:
            st.info(f"➡️ IV vs HV: {iv_premium:.1f}% - Neutral")
    
    st.divider()
    
    # STRATEGIEKOMBINATIONEN
    st.subheader("🎯 Strategiekombinationen")
    
    current_price = metrics.get('current_price', 0)
    strategy_options = analyzer.get_strategy_options()
    
    # ATR für Strike-Berechnung
    if not history.empty:
        history = analyzer.calculate_atr(history)
        atr = history['ATR'].iloc[-1] if 'ATR' in history.columns else current_price * 0.02
    else:
        atr = current_price * 0.02
    
    # Bollinger Bänder
    if not history.empty:
        history = analyzer.calculate_bollinger_bands(history)
        bb_upper = history['BB_Upper'].iloc[-1]
        bb_lower = history['BB_Lower'].iloc[-1]
    else:
        bb_upper = current_price * 1.05
        bb_lower = current_price * 0.95
    
    st.markdown("""
    <div class="strategy-box">
    <h4>📊 Strategie-Übersicht für Hebel ~7x</h4>
    <p>Die Kombinationen sind optimiert für maximale Prämieneinnahme bei kontrolliertem Risiko.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Strategie 1: Langlaufender Call Kauf
    st.markdown("### 1️⃣ Langlaufender Call KAUF (6-12 Monate)")
    
    # Wechselkurs
    fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    
    strategy = strategy_options['long_call_buy']
    if strategy['options'] is not None and not strategy['options'].empty:
        st.write(f"**Verfall:** {strategy['expiration']} ({strategy['days']} Tage)")
        
        # Empfohlene Strikes: ATM oder leicht ITM
        calls = strategy['options']
        
        # Filter auf relevante Strikes
        relevant_calls = calls[(calls['strike'] >= current_price * 0.90) & 
                              (calls['strike'] <= current_price * 1.05)]
        
        if not relevant_calls.empty:
            # Sortieren nach höchstem Open Interest (Liquidität)
            relevant_calls = relevant_calls.sort_values('openInterest', ascending=False)
            
            display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'openInterest', 'impliedVolatility']
            display_df = relevant_calls[display_cols].head(5).copy()
            
            # Währungsumrechnung für Preise
            display_df['strike'] = display_df['strike'] * fx_rate
            display_df['lastPrice'] = display_df['lastPrice'] * fx_rate
            display_df['bid'] = display_df['bid'] * fx_rate
            display_df['ask'] = display_df['ask'] * fx_rate
            display_df['impliedVolatility'] = display_df['impliedVolatility'] * 100
            display_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask', 'Open Interest', 'IV (%)']
            st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)
            
            # Empfehlung
            best_call = relevant_calls.iloc[0]
            strike_chf = best_call['strike'] * fx_rate
            ask_chf = best_call['ask'] * fx_rate
            st.success(f"💡 Empfehlung: Strike {curr_symbol}{strike_chf:.2f} (ATM/leicht ITM) - "
                      f"Prämie ca. {curr_symbol}{ask_chf:.2f} - Hohe Liquidität")
    else:
        st.warning("Keine Optionen im Bereich 6-12 Monate verfügbar")
    
    st.divider()
    
    # Strategie 2: Langlaufender Put Verkauf
    st.markdown("### 2️⃣ Langlaufender Put VERKAUF (12-24 Monate)")
    
    strategy = strategy_options['long_put_sell']
    if strategy['options'] is not None and not strategy['options'].empty:
        st.write(f"**Verfall:** {strategy['expiration']} ({strategy['days']} Tage)")
        
        puts = strategy['options']
        
        # Filter auf OTM Puts (10-20% unter aktuellem Kurs)
        relevant_puts = puts[(puts['strike'] >= current_price * 0.80) & 
                            (puts['strike'] <= current_price * 0.95)]
        
        if not relevant_puts.empty:
            relevant_puts = relevant_puts.sort_values('bid', ascending=False)
            
            display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'openInterest', 'impliedVolatility']
            display_df = relevant_puts[display_cols].head(5).copy()
            
            # Währungsumrechnung
            display_df['strike'] = display_df['strike'] * fx_rate
            display_df['lastPrice'] = display_df['lastPrice'] * fx_rate
            display_df['bid'] = display_df['bid'] * fx_rate
            display_df['ask'] = display_df['ask'] * fx_rate
            display_df['impliedVolatility'] = display_df['impliedVolatility'] * 100
            display_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask', 'Open Interest', 'IV (%)']
            st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)
            
            # Empfehlung: Höchste Prämie
            best_put = relevant_puts.iloc[0]
            strike_chf = best_put['strike'] * fx_rate
            bid_chf = best_put['bid'] * fx_rate
            st.success(f"💡 Empfehlung: Strike {curr_symbol}{strike_chf:.2f} ({((best_put['strike']/current_price)-1)*100:.1f}% OTM) - "
                      f"Prämie ca. {curr_symbol}{bid_chf:.2f} - Hohe Prämie!")
    else:
        st.warning("Keine Optionen im Bereich 12-24 Monate verfügbar")
    
    st.divider()
    
    # Strategie 3: Sicherungs-Put Kauf
    st.markdown("### 3️⃣ Sicherungs-Put KAUF (3-6 Monate)")
    
    strategy = strategy_options['hedge_put_buy']
    if strategy['options'] is not None and not strategy['options'].empty:
        st.write(f"**Verfall:** {strategy['expiration']} ({strategy['days']} Tage)")
        
        puts = strategy['options']
        
        # Filter auf OTM Puts für Absicherung (15-25% unter Kurs)
        relevant_puts = puts[(puts['strike'] >= current_price * 0.75) & 
                            (puts['strike'] <= current_price * 0.90)]
        
        if not relevant_puts.empty:
            relevant_puts = relevant_puts.sort_values('ask', ascending=True)
            
            display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'openInterest', 'impliedVolatility']
            display_df = relevant_puts[display_cols].head(5).copy()
            
            # Währungsumrechnung
            display_df['strike'] = display_df['strike'] * fx_rate
            display_df['lastPrice'] = display_df['lastPrice'] * fx_rate
            display_df['bid'] = display_df['bid'] * fx_rate
            display_df['ask'] = display_df['ask'] * fx_rate
            display_df['impliedVolatility'] = display_df['impliedVolatility'] * 100
            display_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask', 'Open Interest', 'IV (%)']
            st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)
            
            # Empfehlung: Günstigste Absicherung
            best_hedge = relevant_puts.iloc[0]
            strike_chf = best_hedge['strike'] * fx_rate
            ask_chf = best_hedge['ask'] * fx_rate
            st.info(f"💡 Empfehlung: Strike {curr_symbol}{strike_chf:.2f} ({((best_hedge['strike']/current_price)-1)*100:.1f}% OTM) - "
                   f"Kosten ca. {curr_symbol}{ask_chf:.2f} - Günstige Absicherung")
    else:
        st.warning("Keine Optionen im Bereich 3-6 Monate verfügbar")
    
    st.divider()
    
    # Strategie 4: Kurzlaufender Call Verkauf
    st.markdown("### 4️⃣ Kurzlaufender Call VERKAUF (wöchentlich)")
    
    strategy = strategy_options['short_call_sell']
    if strategy['options'] is not None and not strategy['options'].empty:
        st.write(f"**Verfall:** {strategy['expiration']} ({strategy['days']} Tage)")
        
        calls = strategy['options']
        
        # Filter auf OTM Calls (1-2 ATR über aktuellem Kurs)
        lower_strike = current_price + atr
        upper_strike = current_price + (3 * atr)
        
        relevant_calls = calls[(calls['strike'] >= lower_strike) & 
                              (calls['strike'] <= upper_strike)]
        
        if not relevant_calls.empty:
            relevant_calls = relevant_calls.sort_values('bid', ascending=False)
            
            display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'openInterest', 'impliedVolatility']
            display_df = relevant_calls[display_cols].head(5).copy()
            
            # Währungsumrechnung
            display_df['strike'] = display_df['strike'] * fx_rate
            display_df['lastPrice'] = display_df['lastPrice'] * fx_rate
            display_df['bid'] = display_df['bid'] * fx_rate
            display_df['ask'] = display_df['ask'] * fx_rate
            display_df['impliedVolatility'] = display_df['impliedVolatility'] * 100
            display_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask', 'Open Interest', 'IV (%)']
            st.dataframe(display_df.round(2), use_container_width=True, hide_index=True)
            
            # Empfehlung
            best_call = relevant_calls.iloc[0]
            strike_chf = best_call['strike'] * fx_rate
            bid_chf = best_call['bid'] * fx_rate
            st.success(f"💡 Empfehlung: Strike {curr_symbol}{strike_chf:.2f} ({((best_call['strike']/current_price)-1)*100:.1f}% OTM) - "
                      f"Prämie ca. {curr_symbol}{bid_chf:.2f}")
    else:
        st.warning("Keine wöchentlichen Optionen verfügbar")
    
    st.divider()
    
    # STRATEGIEVERGLEICH
    st.subheader("📊 Strategievergleich")
    
    comparison_data = []
    
    strategies = [
        ('Long Call Kauf', '6-12 Mo', strategy_options['long_call_buy'], 'calls', 'DEBIT'),
        ('Long Put Verkauf', '12-24 Mo', strategy_options['long_put_sell'], 'puts', 'CREDIT'),
        ('Hedge Put Kauf', '3-6 Mo', strategy_options['hedge_put_buy'], 'puts', 'DEBIT'),
        ('Short Call Verkauf', 'Wöchentl.', strategy_options['short_call_sell'], 'calls', 'CREDIT'),
    ]
    
    for name, timeframe, strat, opt_type, cash_flow in strategies:
        if strat['options'] is not None and not strat['options'].empty:
            opts = strat['options']
            
            if cash_flow == 'CREDIT':
                best = opts.sort_values('bid', ascending=False).iloc[0]
                premium = best['bid']
            else:
                best = opts.sort_values('ask', ascending=True).iloc[0]
                premium = best['ask']
            
            iv = best.get('impliedVolatility', 0) * 100
            oi = best.get('openInterest', 0)
            
            # Währungsumrechnung
            strike_conv = best['strike'] * fx_rate
            premium_conv = premium * fx_rate
            
            comparison_data.append({
                'Strategie': name,
                'Laufzeit': timeframe,
                f'Strike ({target_currency})': f"{curr_symbol}{strike_conv:.2f}",
                f'Prämie ({target_currency})': f"{curr_symbol}{premium_conv:.2f}",
                'Cash Flow': cash_flow,
                'IV (%)': f"{iv:.1f}%",
                'Open Interest': int(oi)
            })
    
    if comparison_data:
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        # Netto Cash Flow berechnen
        total_credit = sum([float(d[f'Prämie ({target_currency})'].replace(curr_symbol, '').replace(',', '')) 
                          for d in comparison_data if d['Cash Flow'] == 'CREDIT'])
        total_debit = sum([float(d[f'Prämie ({target_currency})'].replace(curr_symbol, '').replace(',', '')) 
                         for d in comparison_data if d['Cash Flow'] == 'DEBIT'])
        net_cash = total_credit - total_debit
        
        if net_cash > 0:
            st.success(f"💰 Netto Credit (Einnahme): {curr_symbol}{net_cash:.2f} pro Aktie / {curr_symbol}{net_cash*100:.2f} pro Kontrakt")
        else:
            st.warning(f"💸 Netto Debit (Ausgabe): {curr_symbol}{abs(net_cash):.2f} pro Aktie / {curr_symbol}{abs(net_cash)*100:.2f} pro Kontrakt")
    
    st.divider()
    
    # Margin-Schätzung
    st.subheader(f"💰 Margin- und Hebel-Schätzung (in {target_currency})")
    
    position_value = current_price * 100 * fx_rate  # 1 Kontrakt = 100 Aktien, umgerechnet
    
    margin_cols = st.columns(3)
    
    with margin_cols[0]:
        put_margin = position_value * 0.20
        st.metric("Geschätzte Put-Margin (pro Kontrakt)", 
                  f"{curr_symbol}{put_margin:,.0f}",
                  help="Ungefähre Margin für einen verkauften Put")
    
    with margin_cols[1]:
        leverage_7_capital = position_value / 7
        st.metric("Kapital bei Hebel 7 (pro Kontrakt)",
                  f"{curr_symbol}{leverage_7_capital:,.0f}",
                  help="Benötigtes Eigenkapital bei 7-fachem Hebel")
    
    with margin_cols[2]:
        st.metric("Kontrollierter Wert (1 Kontrakt)",
                  f"{curr_symbol}{position_value:,.0f}",
                  help="Wert von 100 Aktien")
    
    # Optionsketten anzeigen
    if options_info['chains']:
        st.divider()
        st.subheader("📊 Optionsketten (Detailansicht)")
        
        selected_exp = st.selectbox(
            "Verfalltermin auswählen",
            options=list(options_info['chains'].keys())
        )
        
        if selected_exp in options_info['chains']:
            chain = options_info['chains'][selected_exp]
            
            tab_calls, tab_puts = st.tabs(["Calls", "Puts"])
            
            with tab_calls:
                calls_df = chain['calls'][['strike', 'lastPrice', 'bid', 'ask', 
                                           'volume', 'openInterest', 'impliedVolatility']].copy()
                # Währungsumrechnung
                calls_df['strike'] = calls_df['strike'] * fx_rate
                calls_df['lastPrice'] = calls_df['lastPrice'] * fx_rate
                calls_df['bid'] = calls_df['bid'] * fx_rate
                calls_df['ask'] = calls_df['ask'] * fx_rate
                calls_df['impliedVolatility'] = calls_df['impliedVolatility'] * 100
                calls_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask', 
                                   'Volume', 'Open Interest', 'IV (%)']
                calls_df = calls_df.round(2)
                st.dataframe(calls_df, use_container_width=True)
            
            with tab_puts:
                puts_df = chain['puts'][['strike', 'lastPrice', 'bid', 'ask',
                                         'volume', 'openInterest', 'impliedVolatility']].copy()
                # Währungsumrechnung
                puts_df['strike'] = puts_df['strike'] * fx_rate
                puts_df['lastPrice'] = puts_df['lastPrice'] * fx_rate
                puts_df['bid'] = puts_df['bid'] * fx_rate
                puts_df['ask'] = puts_df['ask'] * fx_rate
                puts_df['impliedVolatility'] = puts_df['impliedVolatility'] * 100
                puts_df.columns = [f'Strike ({target_currency})', 'Letzter Preis', 'Bid', 'Ask',
                                  'Volume', 'Open Interest', 'IV (%)']
                puts_df = puts_df.round(2)
                st.dataframe(puts_df, use_container_width=True)


def generate_summary(analyzer: StockAnalyzer, metrics: dict, thumbs: dict) -> str:
    """Generiert eine Zusammenfassung zum Abspeichern"""
    
    div_yield = metrics.get('dividend_yield', 0)
    
    summary = f"""
================================================================================
                    AKTIENANALYSE-ZUSAMMENFASSUNG
                    {datetime.now().strftime('%d.%m.%Y %H:%M')}
================================================================================

TICKER: {analyzer.ticker}
NAME: {metrics.get('name', 'N/A')}
SEKTOR: {metrics.get('sector', 'N/A')}
INDUSTRIE: {metrics.get('industry', 'N/A')}

--------------------------------------------------------------------------------
                         PREISDATEN
--------------------------------------------------------------------------------
Aktueller Kurs:     ${metrics.get('current_price', 0):,.2f}
52-Wochen-Hoch:     ${metrics.get('52w_high', 0):,.2f}
52-Wochen-Tief:     ${metrics.get('52w_low', 0):,.2f}
Marktkapitalisierung: {format_number(metrics.get('market_cap', 0), 'currency')}

--------------------------------------------------------------------------------
                      BEWERTUNGSKENNZAHLEN
--------------------------------------------------------------------------------
P/E Ratio (TTM):    {metrics.get('pe_ratio', 0):.2f}
Forward P/E:        {metrics.get('forward_pe', 0):.2f}
Price to Book:      {metrics.get('price_to_book', 0):.2f}
Price to FCF:       {metrics.get('price_to_fcf', 0):.2f}
FCF Yield:          {metrics.get('fcf_yield', 0):.2f}%

--------------------------------------------------------------------------------
                         DIVIDENDE
--------------------------------------------------------------------------------
Dividendenrendite:  {div_yield:.2f}%
Dividende (p.a.):   ${metrics.get('dividend_rate', 0):.2f}
Ausschüttungsquote: {metrics.get('payout_ratio', 0)*100:.2f}%

--------------------------------------------------------------------------------
                       RISIKOKENNZAHLEN
--------------------------------------------------------------------------------
Beta:               {metrics.get('beta', 0):.2f}
Debt/Equity:        {metrics.get('debt_to_equity', 0):.2f}
Current Ratio:      {metrics.get('current_ratio', 0):.2f}

--------------------------------------------------------------------------------
                      3-DAUMEN-REGEL
--------------------------------------------------------------------------------
Gesamt:             {thumbs['total_thumbs']}/3 Daumen

Daumen 1 (>200 SMA): {'✓ JA' if thumbs['thumb1']['value'] else '✗ NEIN'}
  → Abstand zur SMA200: {thumbs['details'].get('price_vs_sma200', 0):.2f}%

Daumen 2 (YTD +):    {'✓ JA' if thumbs['thumb2']['value'] else '✗ NEIN'}
  → YTD Return: {thumbs['details'].get('ytd_return', 0):.2f}%

Daumen 3 (Jahresregel): {'✓ JA' if thumbs['thumb3']['value'] else '✗ NEIN'}
  → {thumbs['thumb3']['description']}
  → Erste 5 Tage: {thumbs['details'].get('first_5_days_return', 0):.2f}%

BEWERTUNG: {'SEHR GUT - Alle Daumen positiv' if thumbs['total_thumbs'] == 3 
            else 'GUT - 2 von 3 Daumen positiv' if thumbs['total_thumbs'] == 2 
            else 'VORSICHT - Weniger als 2 Daumen positiv'}

--------------------------------------------------------------------------------
                     OPTIONSSTRATEGIE-KOMBINATIONEN
--------------------------------------------------------------------------------
1. Langlaufender Call KAUF (6-12 Monate): ATM oder leicht ITM
2. Langlaufender Put VERKAUF (12-24 Monate): 10-20% OTM
3. Sicherungs-Put KAUF (3-6 Monate): 15-25% OTM  
4. Kurzlaufender Call VERKAUF (wöchentlich): 1-2 ATR über Kurs

Ziel: Hebel ~7x, maximale Prämieneinnahme, kontrolliertes Risiko

================================================================================
                        DISCLAIMER
================================================================================
Diese Analyse dient nur zu Informationszwecken und stellt keine Anlageberatung 
dar. Investitionen in Optionen sind mit erheblichen Risiken verbunden. 
Konsultieren Sie einen Finanzberater vor Anlageentscheidungen.
================================================================================
"""
    return summary


# ============================================================================
#                       STRATEGIE-BUILDER FUNKTIONEN
# ============================================================================

def calculate_strategy_combinations(analyzer: StockAnalyzer, metrics: dict, 
                                   target_risk: float = 5000,
                                   source_currency: str = 'USD',
                                   target_currency: str = 'CHF') -> dict:
    """
    Berechnet optimale Optionskombinationen basierend auf:
    1. Long Call (6-12 Mo) + Short Put (12-24 Mo) + Long Hedge Put (3-6 Mo)
    2. Risiko-Ziel von ~5000 in Zielwährung
    3. Maximierung der Prämienrendite
    """
    
    result = {
        'combinations': [],
        'best_combination': None,
        'short_call_recommendations': [],
        'market_signals': {},
        'fx_rate': 1.0
    }
    
    current_price = metrics.get('current_price', 0)
    if current_price <= 0:
        return result
    
    # Wechselkurs
    fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    result['fx_rate'] = fx_rate
    
    # Dividendenrendite als Benchmark
    div_yield = metrics.get('dividend_yield', 0) / 100  # in Dezimal
    
    # Optionsketten holen
    strategy_options = analyzer.get_strategy_options()
    
    # Prüfen ob alle benötigten Optionen verfügbar sind
    long_call = strategy_options.get('long_call_buy', {})
    short_put = strategy_options.get('long_put_sell', {})
    hedge_put = strategy_options.get('hedge_put_buy', {})
    
    if (long_call.get('options') is None or long_call['options'].empty or
        short_put.get('options') is None or short_put['options'].empty or
        hedge_put.get('options') is None or hedge_put['options'].empty):
        return result
    
    # Kombinationen generieren
    combinations = []
    
    # Long Calls filtern (ATM bis leicht ITM)
    long_calls = long_call['options']
    atm_calls = long_calls[(long_calls['strike'] >= current_price * 0.95) & 
                           (long_calls['strike'] <= current_price * 1.05)]
    atm_calls = atm_calls.sort_values('openInterest', ascending=False).head(3)
    
    # Short Puts filtern (10-20% OTM)
    short_puts = short_put['options']
    otm_puts = short_puts[(short_puts['strike'] >= current_price * 0.80) & 
                          (short_puts['strike'] <= current_price * 0.92)]
    otm_puts = otm_puts.sort_values('bid', ascending=False).head(3)
    
    # Hedge Puts filtern (15-25% OTM)
    hedge_puts = hedge_put['options']
    hedge_options = hedge_puts[(hedge_puts['strike'] >= current_price * 0.75) & 
                               (hedge_puts['strike'] <= current_price * 0.88)]
    hedge_options = hedge_options.sort_values('ask', ascending=True).head(3)
    
    # Alle Kombinationen durchgehen
    for _, call in atm_calls.iterrows():
        for _, put in otm_puts.iterrows():
            for _, hedge in hedge_options.iterrows():
                # Kosten und Einnahmen berechnen
                call_cost = call['ask'] * 100  # pro Kontrakt
                put_income = put['bid'] * 100
                hedge_cost = hedge['ask'] * 100
                
                # Netto-Kosten der Basis-Kombination
                net_cost = call_cost - put_income + hedge_cost
                
                # Max Risiko = Strike des verkauften Puts - Strike des Hedge Puts + Netto-Kosten
                max_risk_per_contract = (put['strike'] - hedge['strike']) * 100 + max(0, net_cost)
                
                # Wenn Risiko negativ (wir bekommen Geld), setze auf minimales Risiko
                if max_risk_per_contract <= 0:
                    max_risk_per_contract = abs(net_cost) if net_cost < 0 else call_cost
                
                # Anzahl Kontrakte für Ziel-Risiko
                target_risk_usd = target_risk / fx_rate
                num_contracts = max(1, int(target_risk_usd / max_risk_per_contract))
                
                # Tatsächliches Risiko
                actual_risk = max_risk_per_contract * num_contracts
                
                # Prämienrendite berechnen (annualisiert)
                # Credit = Put-Prämie - Hedge-Kosten
                net_premium = put['bid'] - hedge['ask']
                
                # Kapitalbindung = Call-Kosten + Hedge-Kosten (oder Margin für Put)
                capital_required = call_cost + hedge_cost
                
                # Annualisierte Rendite
                days_to_expiry = min(long_call.get('days', 365), short_put.get('days', 365))
                annual_factor = 365 / max(days_to_expiry, 30)
                
                if capital_required > 0:
                    premium_yield = (net_premium * 100 / capital_required) * annual_factor
                else:
                    premium_yield = 0
                
                # Delta-Approximation für Kursanpassung
                call_delta = 0.5 + 0.5 * (1 - call['strike'] / current_price) if call['strike'] <= current_price else 0.5 - 0.3 * (call['strike'] / current_price - 1)
                call_delta = max(0.3, min(0.8, call_delta))
                
                combination = {
                    'long_call': {
                        'strike': call['strike'],
                        'expiry': long_call.get('expiration', 'N/A'),
                        'days': long_call.get('days', 0),
                        'premium': call['ask'],
                        'iv': call.get('impliedVolatility', 0) * 100,
                        'delta': call_delta
                    },
                    'short_put': {
                        'strike': put['strike'],
                        'expiry': short_put.get('expiration', 'N/A'),
                        'days': short_put.get('days', 0),
                        'premium': put['bid'],
                        'iv': put.get('impliedVolatility', 0) * 100,
                        'otm_pct': (1 - put['strike'] / current_price) * 100
                    },
                    'hedge_put': {
                        'strike': hedge['strike'],
                        'expiry': hedge_put.get('expiration', 'N/A'),
                        'days': hedge_put.get('days', 0),
                        'premium': hedge['ask'],
                        'iv': hedge.get('impliedVolatility', 0) * 100,
                        'otm_pct': (1 - hedge['strike'] / current_price) * 100
                    },
                    'num_contracts': num_contracts,
                    'net_cost': net_cost * num_contracts,
                    'max_risk': actual_risk,
                    'max_risk_chf': actual_risk * fx_rate,
                    'premium_yield': premium_yield,
                    'vs_dividend': premium_yield - (div_yield * 100),
                    'capital_required': capital_required * num_contracts,
                    'capital_required_chf': capital_required * num_contracts * fx_rate,
                    'upside_participation': call_delta
                }
                
                combinations.append(combination)
    
    # Nach Prämienrendite sortieren
    combinations.sort(key=lambda x: x['premium_yield'], reverse=True)
    result['combinations'] = combinations[:5]  # Top 5
    
    if combinations:
        result['best_combination'] = combinations[0]
    
    return result


def calculate_short_call_signals(analyzer: StockAnalyzer, metrics: dict,
                                 num_base_contracts: int = 1) -> dict:
    """
    Berechnet Empfehlungen für kurzfristige Call-Verkäufe basierend auf:
    - MACD-Signal
    - Abstand zur 200-Tage-Linie
    - Saisonalität (Wochenbasis)
    """
    
    signals = {
        'macd_signal': 0,
        'sma200_signal': 0,
        'seasonality_signal': 0,
        'combined_score': 0,
        'recommendation': '',
        'num_calls_to_sell': 0,
        'strike_recommendation': 0,
        'details': {}
    }
    
    current_price = metrics.get('current_price', 0)
    if current_price <= 0:
        return signals
    
    # Historische Daten laden
    history = analyzer.get_history("1y")
    if history.empty:
        return signals
    
    # Timezone entfernen
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)
    
    # MACD berechnen
    history = analyzer.calculate_macd(history)
    
    # 200-Tage SMA berechnen
    history = analyzer.calculate_moving_averages(history)
    
    # ATR berechnen
    history = analyzer.calculate_atr(history)
    
    # 1. MACD-Signal (-1 bis +1)
    if 'MACD' in history.columns and 'MACD_Signal' in history.columns:
        macd = history['MACD'].iloc[-1]
        macd_signal = history['MACD_Signal'].iloc[-1]
        macd_histogram = history['MACD_Histogram'].iloc[-1] if 'MACD_Histogram' in history.columns else macd - macd_signal
        
        # MACD unter Signal = bearish = gut für Call-Verkauf
        if macd < macd_signal:
            signals['macd_signal'] = min(1.0, abs(macd_histogram) / (current_price * 0.01))
        else:
            signals['macd_signal'] = -min(1.0, abs(macd_histogram) / (current_price * 0.01))
        
        signals['details']['macd'] = macd
        signals['details']['macd_signal_line'] = macd_signal
        signals['details']['macd_histogram'] = macd_histogram
    
    # 2. Abstand zur 200-Tage-Linie (-1 bis +1)
    if 'SMA_200' in history.columns:
        sma_200 = history['SMA_200'].iloc[-1]
        distance_pct = (current_price - sma_200) / sma_200 * 100
        
        # Weit über SMA200 = überkauft = gut für Call-Verkauf
        if distance_pct > 5:
            signals['sma200_signal'] = min(1.0, (distance_pct - 5) / 10)
        elif distance_pct < -5:
            signals['sma200_signal'] = -min(1.0, abs(distance_pct + 5) / 10)
        else:
            signals['sma200_signal'] = 0
        
        signals['details']['sma_200'] = sma_200
        signals['details']['distance_to_sma200_pct'] = distance_pct
    
    # 3. Saisonalität (-1 bis +1)
    seasonal_data = analyzer.get_seasonal_data()
    if not seasonal_data.empty:
        current_week = datetime.now().isocalendar()[1]
        
        # Finde aktuelle Woche in den saisonalen Daten
        if current_week in seasonal_data['Week'].values:
            week_data = seasonal_data[seasonal_data['Week'] == current_week].iloc[0]
            avg_return = week_data['Avg_Return_Pct']
            positive_pct = week_data['Positive_Pct']
            
            # Negative saisonale Tendenz = gut für Call-Verkauf
            if avg_return < -0.5:
                signals['seasonality_signal'] = min(1.0, abs(avg_return) / 2)
            elif avg_return > 0.5:
                signals['seasonality_signal'] = -min(1.0, avg_return / 2)
            else:
                signals['seasonality_signal'] = 0
            
            signals['details']['current_week'] = current_week
            signals['details']['seasonal_avg_return'] = avg_return
            signals['details']['seasonal_positive_pct'] = positive_pct
    
    # Kombinierter Score (gewichtet)
    weights = {'macd': 0.4, 'sma200': 0.35, 'seasonality': 0.25}
    signals['combined_score'] = (
        signals['macd_signal'] * weights['macd'] +
        signals['sma200_signal'] * weights['sma200'] +
        signals['seasonality_signal'] * weights['seasonality']
    )
    
    # Empfehlung basierend auf Score
    base_contracts = num_base_contracts
    target_50_pct = max(1, int(base_contracts * 0.5))
    
    if signals['combined_score'] >= 0.5:
        signals['recommendation'] = 'STARK VERKAUFEN'
        signals['num_calls_to_sell'] = target_50_pct
    elif signals['combined_score'] >= 0.2:
        signals['recommendation'] = 'MODERAT VERKAUFEN'
        signals['num_calls_to_sell'] = max(1, int(target_50_pct * 0.7))
    elif signals['combined_score'] >= 0:
        signals['recommendation'] = 'LEICHT VERKAUFEN'
        signals['num_calls_to_sell'] = max(1, int(target_50_pct * 0.5))
    elif signals['combined_score'] >= -0.3:
        signals['recommendation'] = 'ABWARTEN'
        signals['num_calls_to_sell'] = 0
    else:
        signals['recommendation'] = 'NICHT VERKAUFEN'
        signals['num_calls_to_sell'] = 0
    
    # Strike-Empfehlung (1-2 ATR über aktuellem Kurs)
    if 'ATR' in history.columns:
        atr = history['ATR'].iloc[-1]
        
        # Bei starkem Signal: näher am Geld, bei schwachem: weiter weg
        if signals['combined_score'] >= 0.5:
            signals['strike_recommendation'] = current_price + (1.0 * atr)
        elif signals['combined_score'] >= 0.2:
            signals['strike_recommendation'] = current_price + (1.5 * atr)
        else:
            signals['strike_recommendation'] = current_price + (2.0 * atr)
        
        signals['details']['atr'] = atr
    
    return signals


def calculate_exit_signals(combination: dict, current_price: float, 
                          original_price: float) -> dict:
    """
    Berechnet Wechsel-/Exit-Signale für die Optionskombination.
    """
    
    exits = {
        'long_call_exit': None,
        'short_put_exit': None,
        'hedge_put_exit': None,
        'overall_action': 'HALTEN'
    }
    
    if not combination:
        return exits
    
    price_change_pct = (current_price - original_price) / original_price * 100
    
    long_call = combination.get('long_call', {})
    short_put = combination.get('short_put', {})
    hedge_put = combination.get('hedge_put', {})
    
    # Long Call Exit-Signale
    if long_call:
        days_left = long_call.get('days', 365)
        call_strike = long_call.get('strike', current_price)
        
        if current_price > call_strike * 1.20:  # 20% ITM
            exits['long_call_exit'] = {
                'action': 'ROLLEN ODER SCHLIESSEN',
                'reason': f'Call ist 20%+ ITM - Gewinne realisieren oder auf höheren Strike rollen',
                'urgency': 'HOCH'
            }
        elif days_left < 30 and current_price > call_strike:
            exits['long_call_exit'] = {
                'action': 'ROLLEN',
                'reason': f'Nur noch {days_left} Tage - auf längere Laufzeit rollen',
                'urgency': 'MITTEL'
            }
        elif current_price < call_strike * 0.85:  # 15% OTM
            exits['long_call_exit'] = {
                'action': 'BEOBACHTEN',
                'reason': 'Call ist 15%+ OTM - bei Erholung ggf. anpassen',
                'urgency': 'NIEDRIG'
            }
    
    # Short Put Exit-Signale
    if short_put:
        days_left = short_put.get('days', 365)
        put_strike = short_put.get('strike', current_price * 0.85)
        
        if current_price < put_strike * 1.05:  # Nahe am Strike
            exits['short_put_exit'] = {
                'action': 'ROLLEN NACH UNTEN',
                'reason': f'Kurs nähert sich Put-Strike - auf niedrigeren Strike rollen',
                'urgency': 'HOCH'
            }
        elif current_price > put_strike * 1.30:  # 30% über Strike
            exits['short_put_exit'] = {
                'action': 'SCHLIESSEN UND NEU VERKAUFEN',
                'reason': 'Put weit OTM - Prämie einsammeln und neuen verkaufen',
                'urgency': 'MITTEL'
            }
        elif days_left < 60:
            exits['short_put_exit'] = {
                'action': 'ROLLEN',
                'reason': f'Nur noch {days_left} Tage - auf längere Laufzeit rollen',
                'urgency': 'MITTEL'
            }
    
    # Hedge Put Exit-Signale
    if hedge_put:
        days_left = hedge_put.get('days', 180)
        
        if days_left < 30:
            exits['hedge_put_exit'] = {
                'action': 'ROLLEN',
                'reason': f'Hedge läuft aus - neuen Hedge kaufen',
                'urgency': 'HOCH'
            }
        elif price_change_pct > 15:  # Starker Anstieg
            exits['hedge_put_exit'] = {
                'action': 'REDUZIEREN',
                'reason': 'Bei starkem Anstieg: Hedge-Kosten reduzieren',
                'urgency': 'NIEDRIG'
            }
    
    # Gesamt-Empfehlung
    high_urgency = sum(1 for e in [exits['long_call_exit'], exits['short_put_exit'], exits['hedge_put_exit']] 
                       if e and e.get('urgency') == 'HOCH')
    
    if high_urgency >= 2:
        exits['overall_action'] = 'DRINGEND ANPASSEN'
    elif high_urgency == 1:
        exits['overall_action'] = 'ANPASSUNG PRÜFEN'
    else:
        exits['overall_action'] = 'HALTEN'
    
    return exits




# ============================================================================
#                       BLACK-SCHOLES BEWERTUNG
# ============================================================================


# ============================================================================
#                       BLACK-SCHOLES BEWERTUNG
# ============================================================================

def black_scholes(S: float, K: float, T: float, r: float, sigma: float, 
                  option_type: str = 'call') -> float:
    """Black-Scholes Optionsbewertung."""
    if T <= 0:
        if option_type == 'call':
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    if sigma <= 0:
        sigma = 0.001
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    return max(0, price)


def calculate_historical_volatility(prices: pd.Series, window: int = 30) -> float:
    """Berechnet die historische Volatilität."""
    if len(prices) < window:
        window = len(prices)
    if window < 2:
        return 0.20
    
    recent_prices = prices.tail(window)
    log_returns = np.log(recent_prices / recent_prices.shift(1)).dropna()
    
    if len(log_returns) < 2:
        return 0.20
    
    daily_vol = log_returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    
    return max(0.05, min(1.0, annual_vol))


def get_available_strikes(analyzer: StockAnalyzer) -> list:
    """Holt verfügbare Strikes aus der Optionskette (unskaliert)."""
    strikes = []
    try:
        options = analyzer.get_options_chain()
        if options and 'calls' in options and not options['calls'].empty:
            strikes = sorted(options['calls']['strike'].unique())
    except:
        pass
    return strikes


def find_nearest_strike(price: float, available_strikes: list, direction: str = 'above') -> float:
    """Findet den nächsten verfügbaren Strike aus der Optionskette."""
    if not available_strikes:
        # Fallback: Standard-Strike-Abstände verwenden
        if price < 20:
            # Unter $20: 0.50 Abstände
            if direction == 'above':
                return round((price + 0.25) * 2) / 2
            else:
                return round((price - 0.25) * 2) / 2
        elif price < 50:
            # $20-50: 1.00 Abstände
            if direction == 'above':
                return round(price + 0.5)
            else:
                return round(price - 0.5)
        else:
            # Über $50: 2.50 oder 5.00 Abstände
            if direction == 'above':
                return round((price + 2.5) / 5) * 5
            else:
                return round((price - 2.5) / 5) * 5
    
    if direction == 'above':
        above = [s for s in available_strikes if s > price]
        return min(above) if above else max(available_strikes)
    else:
        below = [s for s in available_strikes if s < price]
        return max(below) if below else min(available_strikes)


def is_market_open() -> tuple:
    """
    Prüft ob die US-Börse (NYSE/NASDAQ) gerade geöffnet ist.
    
    Returns:
        (is_open: bool, message: str)
    """
    try:
        # US Eastern Time
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        # Wochentag (0=Montag, 6=Sonntag)
        weekday = now_et.weekday()
        hour = now_et.hour
        minute = now_et.minute
        
        # Wochenende
        if weekday >= 5:
            return False, f"⚠️ Börse geschlossen (Wochenende). Optionspreise können ungenau sein."
        
        # Handelszeiten: 9:30 - 16:00 ET
        market_open = (hour == 9 and minute >= 30) or (hour >= 10 and hour < 16)
        
        if not market_open:
            if hour < 9 or (hour == 9 and minute < 30):
                return False, f"⚠️ Börse noch nicht geöffnet (Pre-Market). Optionspreise können ungenau sein."
            else:
                return False, f"⚠️ Börse geschlossen (After-Hours). Optionspreise können ungenau sein."
        
        return True, ""
        
    except Exception:
        return True, ""


def validate_strike(strike: float, available_strikes: list) -> tuple:
    """
    Prüft ob ein Strike in der Optionskette existiert.
    
    Returns:
        (is_valid: bool, nearest_strike: float)
    """
    if not available_strikes:
        return True, strike  # Kann nicht validieren
    
    # Exakte Übereinstimmung
    if strike in available_strikes:
        return True, strike
    
    # Finde nächsten Strike
    differences = [(abs(s - strike), s) for s in available_strikes]
    nearest = min(differences, key=lambda x: x[0])[1]
    
    return False, nearest


def run_simple_backtest(analyzer: StockAnalyzer, combination: dict,
                        start_date: datetime, num_days: int,
                        current_price: float,
                        source_currency: str = 'USD',
                        target_currency: str = 'CHF') -> dict:
    """
    Backtest mit echten Strikes aus der Optionskette und Black-Scholes Bewertung.
    
    Die Strikes bleiben unverändert (echte Optionsstrikes).
    Die Kurse werden skaliert um historische Bewegungen auf aktuellen Kurs anzuwenden.
    """
    
    result = {'success': False, 'data': [], 'trades': [], 'final_valuation': {}, 
              'summary': {}, 'warnings': [], 'error': None}
    
    if not combination:
        result['error'] = "Keine Kombination"
        return result
    
    try:
        fx = currency_converter.get_exchange_rate(source_currency, target_currency)
        
        history = analyzer.get_history("2y")
        if history.empty:
            result['error'] = "Keine historischen Daten"
            return result
        
        if history.index.tz is not None:
            history.index = history.index.tz_localize(None)
        
        end_date = start_date + timedelta(days=num_days)
        mask = (history.index >= start_date) & (history.index <= end_date)
        bt_data = history.loc[mask].copy()
        
        if len(bt_data) < 2:
            result['error'] = f"Keine Daten für {start_date.strftime('%Y-%m-%d')}"
            return result
        
        # Skalierung für Kursverlauf (historisch -> aktuell)
        hist_start = bt_data['Close'].iloc[0]
        scale = current_price / hist_start
        
        # Verfügbare Strikes aus aktueller Optionskette (unskaliert!)
        available_strikes = get_available_strikes(analyzer)
        
        n = combination['num_contracts']
        long_call = combination['long_call']
        short_put = combination['short_put']
        hedge_put = combination['hedge_put']
        
        # ECHTE STRIKES aus der Optionskette (NICHT skalieren!)
        call_strike = long_call['strike']
        put_strike = short_put['strike']
        hedge_strike = hedge_put['strike']
        
        # Validiere Strikes
        warnings = []
        for name, strike in [('Long Call', call_strike), ('Short Put', put_strike), ('Hedge Put', hedge_strike)]:
            is_valid, nearest = validate_strike(strike, available_strikes)
            if not is_valid and available_strikes:
                warnings.append(f"Strike {name} ${strike:.2f} nicht in Optionskette. Nächster: ${nearest:.2f}")
        
        result['warnings'] = warnings
        
        call_iv = long_call.get('iv', 20) / 100
        put_iv = short_put.get('iv', 20) / 100
        hedge_iv = hedge_put.get('iv', 25) / 100
        
        call_days_orig = long_call.get('days', 180)
        put_days_orig = short_put.get('days', 365)
        hedge_days_orig = hedge_put.get('days', 90)
        
        risk_free_rate = 0.04
        trades = []
        price_history = []
        
        first_date = bt_data.index[0]
        first_price = bt_data['Close'].iloc[0] * scale  # Skalierter Startkurs
        price_history.append(first_price)
        
        init_vol = (call_iv + put_iv + hedge_iv) / 3
        
        # B&S-Werte für Eröffnung
        call_bs_init = black_scholes(first_price, call_strike, call_days_orig/365, risk_free_rate, init_vol, 'call')
        put_bs_init = black_scholes(first_price, put_strike, put_days_orig/365, risk_free_rate, init_vol, 'put')
        hedge_bs_init = black_scholes(first_price, hedge_strike, hedge_days_orig/365, risk_free_rate, init_vol, 'put')
        
        call_mid = long_call['premium'] if long_call['premium'] > 0 else call_bs_init
        put_mid = short_put['premium'] if short_put['premium'] > 0 else put_bs_init
        hedge_mid = hedge_put['premium'] if hedge_put['premium'] > 0 else hedge_bs_init
        
        trades.append({'date': first_date, 'day': 1, 'action': 'KAUF', 'type': 'Long Call',
            'strike': call_strike, 'expiry_days': call_days_orig,
            'premium': call_mid, 'bs_value': call_bs_init, 'volatility': init_vol,
            'quantity': n, 'total': -call_mid * 100 * n, 'price': first_price})
        
        trades.append({'date': first_date, 'day': 1, 'action': 'VERKAUF', 'type': 'Short Put',
            'strike': put_strike, 'expiry_days': put_days_orig,
            'premium': put_mid, 'bs_value': put_bs_init, 'volatility': init_vol,
            'quantity': n, 'total': put_mid * 100 * n, 'price': first_price})
        
        trades.append({'date': first_date, 'day': 1, 'action': 'KAUF', 'type': 'Hedge Put',
            'strike': hedge_strike, 'expiry_days': hedge_days_orig,
            'premium': hedge_mid, 'bs_value': hedge_bs_init, 'volatility': init_vol,
            'quantity': n, 'total': -hedge_mid * 100 * n, 'price': first_price})
        
        call_cost = call_mid * 100 * n
        put_income = put_mid * 100 * n
        hedge_cost = hedge_mid * 100 * n
        net_investment = call_cost - put_income + hedge_cost
        
        seasonal = analyzer.get_seasonal_data()
        
        data = []
        total_call_income = 0
        prev_week = -1
        short_call_strike = 0
        short_call_premium = 0
        short_call_qty = 0
        short_call_days = 5
        
        for i, (dt, row) in enumerate(bt_data.iterrows()):
            price = row['Close'] * scale
            price_history.append(price)
            pct_change = (price / current_price - 1) * 100
            
            current_vol = calculate_historical_volatility(pd.Series(price_history), min(30, len(price_history)))
            
            week = dt.isocalendar()[1]
            new_week = (week != prev_week)
            days_elapsed = i
            
            if new_week and i > 0 and short_call_qty > 0:
                close_bs = black_scholes(price, short_call_strike, 1/365, risk_free_rate, current_vol, 'call')
                
                if price > short_call_strike:
                    weekly_call_pl = (short_call_premium - (price - short_call_strike)) * 100 * short_call_qty
                else:
                    weekly_call_pl = short_call_premium * 100 * short_call_qty
                
                total_call_income += weekly_call_pl
                
                trades.append({'date': dt, 'day': i + 1, 'action': 'RÜCKKAUF', 'type': 'Short Call (Verfall)',
                    'strike': short_call_strike, 'expiry_days': 0,
                    'premium': close_bs, 'bs_value': close_bs, 'volatility': current_vol,
                    'quantity': short_call_qty, 'total': -close_bs * 100 * short_call_qty,
                    'price': price, 'pl': weekly_call_pl})
                short_call_qty = 0
            
            score = 0.2
            if not seasonal.empty:
                wk = seasonal[seasonal['Week'] == week]
                if not wk.empty:
                    avg_ret = wk['Avg_Return_Pct'].iloc[0]
                    if avg_ret < -0.3:
                        score += 0.3
                    elif avg_ret > 0.3:
                        score -= 0.2
            
            if new_week:
                target = max(1, n // 2)
                if score >= 0.2:
                    short_call_qty = target
                    target_strike = price * 1.015
                    short_call_strike = find_nearest_strike(target_strike, available_strikes, 'above')
                    
                    short_call_T = short_call_days / 365
                    short_call_bs = black_scholes(price, short_call_strike, short_call_T, risk_free_rate, current_vol, 'call')
                    short_call_premium = short_call_bs
                    
                    trades.append({'date': dt, 'day': i + 1, 'action': 'VERKAUF', 'type': 'Short Call (Wöchentlich)',
                        'strike': short_call_strike, 'expiry_days': short_call_days,
                        'premium': short_call_premium, 'bs_value': short_call_bs, 'volatility': current_vol,
                        'quantity': short_call_qty, 'total': short_call_premium * 100 * short_call_qty,
                        'price': price})
                else:
                    short_call_qty = 0
            
            call_days_left = max(0, call_days_orig - days_elapsed)
            put_days_left = max(0, put_days_orig - days_elapsed)
            hedge_days_left = max(0, hedge_days_orig - days_elapsed)
            
            call_val = black_scholes(price, call_strike, call_days_left/365, risk_free_rate, current_vol, 'call') * 100 * n
            put_val = black_scholes(price, put_strike, put_days_left/365, risk_free_rate, current_vol, 'put') * 100 * n
            hedge_val = black_scholes(price, hedge_strike, hedge_days_left/365, risk_free_rate, current_vol, 'put') * 100 * n
            
            base_val = call_val + hedge_val - put_val + put_income - call_cost - hedge_cost
            total_val = base_val + total_call_income
            
            stock_pct = pct_change
            strat_pct = (total_val / abs(net_investment)) * 100 if abs(net_investment) > 0 else 0
            
            data.append({'date': dt, 'day': i + 1, 'price': price, 'pct_change': pct_change,
                'volatility': current_vol, 'score': score, 'call_active': short_call_qty > 0,
                'short_call_strike': short_call_strike if short_call_qty > 0 else None,
                'call_income': total_call_income, 'call_val': call_val, 'put_val': put_val, 'hedge_val': hedge_val,
                'base_value': base_val, 'total_value': total_val, 'strategy_pct': strat_pct, 'stock_pct': stock_pct})
            
            prev_week = week
        
        final_price = data[-1]['price']
        final_date = data[-1]['date']
        num_trading_days = len(data)
        final_vol = data[-1]['volatility']
        
        call_days_left = max(0, call_days_orig - num_trading_days)
        put_days_left = max(0, put_days_orig - num_trading_days)
        hedge_days_left = max(0, hedge_days_orig - num_trading_days)
        
        long_call_bs = black_scholes(final_price, call_strike, call_days_left/365, risk_free_rate, final_vol, 'call')
        short_put_bs = black_scholes(final_price, put_strike, put_days_left/365, risk_free_rate, final_vol, 'put')
        hedge_put_bs = black_scholes(final_price, hedge_strike, hedge_days_left/365, risk_free_rate, final_vol, 'put')
        
        trades.append({'date': final_date, 'day': num_trading_days, 'action': 'VERKAUF', 'type': 'Long Call (Schließen)',
            'strike': call_strike, 'expiry_days': call_days_left,
            'premium': long_call_bs, 'bs_value': long_call_bs, 'volatility': final_vol,
            'quantity': n, 'total': long_call_bs * 100 * n, 'price': final_price})
        
        trades.append({'date': final_date, 'day': num_trading_days, 'action': 'RÜCKKAUF', 'type': 'Short Put (Schließen)',
            'strike': put_strike, 'expiry_days': put_days_left,
            'premium': short_put_bs, 'bs_value': short_put_bs, 'volatility': final_vol,
            'quantity': n, 'total': -short_put_bs * 100 * n, 'price': final_price})
        
        trades.append({'date': final_date, 'day': num_trading_days, 'action': 'VERKAUF', 'type': 'Hedge Put (Schließen)',
            'strike': hedge_strike, 'expiry_days': hedge_days_left,
            'premium': hedge_put_bs, 'bs_value': hedge_put_bs, 'volatility': final_vol,
            'quantity': n, 'total': hedge_put_bs * 100 * n, 'price': final_price})
        
        if short_call_qty > 0:
            final_call_bs = black_scholes(final_price, short_call_strike, 1/365, risk_free_rate, final_vol, 'call')
            if final_price > short_call_strike:
                final_call_pl = (short_call_premium - (final_price - short_call_strike)) * 100 * short_call_qty
            else:
                final_call_pl = short_call_premium * 100 * short_call_qty
            total_call_income += final_call_pl
            
            trades.append({'date': final_date, 'day': num_trading_days, 'action': 'VERFALL', 'type': 'Short Call (Wöchentlich)',
                'strike': short_call_strike, 'expiry_days': 0,
                'premium': final_call_bs, 'bs_value': final_call_bs, 'volatility': final_vol,
                'quantity': short_call_qty, 'total': -final_call_bs * 100 * short_call_qty,
                'price': final_price, 'pl': final_call_pl})
        
        final_valuation = {
            'volatility_30d': final_vol, 'risk_free_rate': risk_free_rate, 'final_price': final_price,
            'long_call': {'strike': call_strike, 'days_left': call_days_left, 'bs_value': long_call_bs, 'total_value': long_call_bs * 100 * n},
            'short_put': {'strike': put_strike, 'days_left': put_days_left, 'bs_value': short_put_bs, 'total_liability': short_put_bs * 100 * n},
            'hedge_put': {'strike': hedge_strike, 'days_left': hedge_days_left, 'bs_value': hedge_put_bs, 'total_value': hedge_put_bs * 100 * n},
            'weekly_calls_income': total_call_income
        }
        
        bs_total = long_call_bs * 100 * n - short_put_bs * 100 * n + hedge_put_bs * 100 * n + total_call_income - net_investment
        final_valuation['net_result'] = bs_total
        final_valuation['net_investment'] = net_investment
        
        data[-1]['call_income'] = total_call_income
        data[-1]['total_value'] = bs_total + net_investment
        data[-1]['strategy_pct'] = (bs_total / abs(net_investment)) * 100 if net_investment != 0 else 0
        
        result['summary'] = {
            'start_date': start_date.strftime('%Y-%m-%d'), 'end_date': end_date.strftime('%Y-%m-%d'),
            'num_days': len(data), 'start_price': current_price, 'end_price': final_price,
            'price_change_pct': data[-1]['pct_change'], 'investment': net_investment,
            'final_value': bs_total + net_investment, 'net_result': bs_total,
            'strategy_pct': data[-1]['strategy_pct'], 'stock_pct': data[-1]['stock_pct'],
            'call_income': total_call_income, 'outperformance': data[-1]['strategy_pct'] - data[-1]['stock_pct'],
            'fx': fx, 'call_strike': call_strike, 'put_strike': put_strike, 'hedge_strike': hedge_strike,
            'volatility_30d': final_vol
        }
        
        result['success'] = True
        result['data'] = data
        result['trades'] = trades
        result['final_valuation'] = final_valuation
        
    except Exception as e:
        result['error'] = str(e)
        import traceback
        result['traceback'] = traceback.format_exc()
    
    return result


def display_backtest(result: dict, curr_symbol: str, target_currency: str):
    """Zeigt Backtest-Ergebnisse mit Trades und B&S Bewertung."""
    
    if not result['success']:
        st.error(f"Fehler: {result.get('error', 'Unbekannt')}")
        if 'traceback' in result:
            with st.expander("Details"):
                st.code(result['traceback'])
        return
    
    s = result['summary']
    data = result['data']
    trades = result.get('trades', [])
    final_val = result.get('final_valuation', {})
    warnings = result.get('warnings', [])
    fx = s.get('fx', 1.0)
    
    st.markdown("### 📊 Backtest-Ergebnis")
    
    # Börsenzeiten-Warnung
    market_open, market_msg = is_market_open()
    if not market_open:
        st.warning(market_msg)
    
    # Strike-Warnungen
    if warnings:
        for w in warnings:
            st.warning(f"⚠️ {w}")
    
    st.info(f"**{s['start_date']}** bis **{s['end_date']}** ({s['num_days']} Handelstage)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Start ({target_currency})", f"{curr_symbol}{s['start_price']*fx:.2f}")
    c2.metric(f"Ende ({target_currency})", f"{curr_symbol}{s['end_price']*fx:.2f}", f"{s['price_change_pct']:+.1f}%")
    c3.metric("Strategie", f"{s['strategy_pct']:+.1f}%", f"{s['outperformance']:+.1f}% vs Aktie")
    c4.metric("Aktie B&H", f"{s['stock_pct']:+.1f}%")
    
    c1b, c2b, c3b, c4b = st.columns(4)
    c1b.metric(f"Investment ({target_currency})", f"{curr_symbol}{s['investment']*fx:,.0f}")
    c2b.metric(f"Endwert ({target_currency})", f"{curr_symbol}{s['final_value']*fx:,.0f}")
    c3b.metric(f"Netto-Ergebnis", f"{curr_symbol}{s['net_result']*fx:+,.0f}")
    c4b.metric("30-Tage Volatilität", f"{s.get('volatility_30d', 0)*100:.1f}%")
    
    st.divider()
    
    st.markdown("### 📝 Alle Transaktionen")
    st.caption("Strikes aus Optionskette | B&S-Wert = Black-Scholes mit aktueller Volatilität")
    
    if trades:
        trade_table = []
        for t in trades:
            trade_table.append({
                'Datum': t['date'].strftime('%Y-%m-%d'),
                'Tag': t['day'],
                'Aktion': t['action'],
                'Typ': t['type'],
                f'Strike ({target_currency})': f"{curr_symbol}{t['strike']*fx:.2f}",
                'Verfall': f"{t.get('expiry_days', 0)}d",
                f'Prämie ({target_currency})': f"{curr_symbol}{t['premium']*fx:.2f}",
                f'B&S-Wert ({target_currency})': f"{curr_symbol}{t.get('bs_value', 0)*fx:.2f}",
                'Vol.': f"{t.get('volatility', 0)*100:.1f}%",
                'Anz.': t['quantity'],
                f'Gesamt ({target_currency})': f"{curr_symbol}{t['total']*fx:+,.0f}",
                f'Kurs ({target_currency})': f"{curr_symbol}{t['price']*fx:.2f}"
            })
        
        st.dataframe(pd.DataFrame(trade_table), use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.markdown("### 📐 Schlussbewertung (Black-Scholes)")
    
    if final_val:
        st.info(f"**Volatilität:** {final_val.get('volatility_30d', 0)*100:.1f}% | **Zinssatz:** {final_val.get('risk_free_rate', 0)*100:.1f}%")
        
        val_cols = st.columns(3)
        
        with val_cols[0]:
            lc = final_val.get('long_call', {})
            st.markdown("**🔵 Long Call**")
            st.write(f"Strike: {curr_symbol}{lc.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {lc.get('days_left', 0)} Tage")
            st.write(f"B&S: {curr_symbol}{lc.get('bs_value', 0)*fx:.2f}")
            st.success(f"**Wert: {curr_symbol}{lc.get('total_value', 0)*fx:,.0f}**")
        
        with val_cols[1]:
            sp = final_val.get('short_put', {})
            st.markdown("**🔴 Short Put**")
            st.write(f"Strike: {curr_symbol}{sp.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {sp.get('days_left', 0)} Tage")
            st.write(f"B&S: {curr_symbol}{sp.get('bs_value', 0)*fx:.2f}")
            st.error(f"**Rückkauf: {curr_symbol}{sp.get('total_liability', 0)*fx:,.0f}**")
        
        with val_cols[2]:
            hp = final_val.get('hedge_put', {})
            st.markdown("**🟡 Hedge Put**")
            st.write(f"Strike: {curr_symbol}{hp.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {hp.get('days_left', 0)} Tage")
            st.write(f"B&S: {curr_symbol}{hp.get('bs_value', 0)*fx:.2f}")
            st.success(f"**Wert: {curr_symbol}{hp.get('total_value', 0)*fx:,.0f}**")
    
    st.divider()
    
    st.markdown("### 📈 Kursverlauf")
    
    if data:
        df = pd.DataFrame(data)
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            row_heights=[0.45, 0.30, 0.25],
            subplot_titles=(f'Kurs ({target_currency})', 'Rendite (%)', 'Volatilität (%)'))
        
        fig.add_trace(go.Scatter(x=df['date'], y=df['price']*fx, name='Kurs', line=dict(color='#2196f3', width=2)), row=1, col=1)
        
        fig.add_hline(y=s['call_strike']*fx, line_dash="dot", line_color="green", annotation_text="Call", row=1, col=1)
        fig.add_hline(y=s['put_strike']*fx, line_dash="dot", line_color="red", annotation_text="Put", row=1, col=1)
        fig.add_hline(y=s['hedge_strike']*fx, line_dash="dot", line_color="orange", annotation_text="Hedge", row=1, col=1)
        
        buy_trades = [t for t in trades if t['action'] in ['KAUF', 'RÜCKKAUF']]
        sell_trades = [t for t in trades if t['action'] == 'VERKAUF']
        
        if buy_trades:
            fig.add_trace(go.Scatter(
                x=[t['date'] for t in buy_trades], y=[t['price']*fx for t in buy_trades],
                mode='markers', name='Käufe', marker=dict(symbol='triangle-up', size=10, color='green'),
                hovertemplate='%{text}<extra></extra>',
                text=[f"{t['type']}<br>Strike: {curr_symbol}{t['strike']*fx:.2f}<br>B&S: {curr_symbol}{t.get('bs_value',0)*fx:.2f}" for t in buy_trades]
            ), row=1, col=1)
        
        if sell_trades:
            fig.add_trace(go.Scatter(
                x=[t['date'] for t in sell_trades], y=[t['price']*fx for t in sell_trades],
                mode='markers', name='Verkäufe', marker=dict(symbol='triangle-down', size=10, color='red'),
                hovertemplate='%{text}<extra></extra>',
                text=[f"{t['type']}<br>Strike: {curr_symbol}{t['strike']*fx:.2f}<br>B&S: {curr_symbol}{t.get('bs_value',0)*fx:.2f}" for t in sell_trades]
            ), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df['date'], y=df['strategy_pct'], name='Strategie', line=dict(color='#4caf50', width=2)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['stock_pct'], name='Aktie', line=dict(color='gray', width=2, dash='dash')), row=2, col=1)
        fig.add_hline(y=0, line_color="black", row=2, col=1)
        
        fig.add_trace(go.Scatter(x=df['date'], y=df['volatility']*100, name='Volatilität', 
            line=dict(color='#ff9800', width=2), fill='tozeroy', fillcolor='rgba(255,152,0,0.2)'), row=3, col=1)
        
        fig.update_layout(height=700, template='plotly_white', legend=dict(orientation="h", y=1.02))
        fig.update_yaxes(title_text=target_currency, row=1, col=1)
        fig.update_yaxes(title_text="%", row=2, col=1)
        fig.update_yaxes(title_text="%", row=3, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("📋 Tägliche Werte"):
        tbl = [{'Datum': d['date'].strftime('%Y-%m-%d'), 'Tag': d['day'],
            f'Kurs ({target_currency})': f"{curr_symbol}{d['price']*fx:.2f}",
            'Änderung': f"{d['pct_change']:+.1f}%", 'Volatilität': f"{d['volatility']*100:.1f}%",
            'Call aktiv': '✓' if d.get('call_active') else '-',
            f'Call-Strike': f"{curr_symbol}{d['short_call_strike']*fx:.2f}" if d.get('short_call_strike') else '-',
            'Strategie %': f"{d['strategy_pct']:+.1f}%", 'Aktie %': f"{d['stock_pct']:+.1f}%"
        } for d in data]
        st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)


def display_strategy_builder(analyzer: StockAnalyzer, metrics: dict,
                            source_currency: str, target_currency: str,
                            curr_symbol: str):
    """Zeigt den Strategie-Builder Tab an."""
    
    st.header("🎯 Strategie-Builder")
    
    st.markdown("""
    <div class="strategy-box">
    <h4>Optimierte Optionskombination</h4>
    <p>Automatische Berechnung von Optionskombinationen für kontrolliertes Risiko und maximale Prämienrendite.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Einstellungen
    col_settings1, col_settings2 = st.columns(2)
    
    with col_settings1:
        target_risk = st.number_input(
            f"Ziel-Risiko ({target_currency})",
            min_value=1000,
            max_value=50000,
            value=5000,
            step=1000,
            help="Maximales Risiko für die Kombination"
        )
    
    with col_settings2:
        current_price = metrics.get('current_price', 0)
        fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
        st.metric(
            f"Aktueller Kurs ({target_currency})",
            f"{curr_symbol}{current_price * fx_rate:.2f}"
        )
    
    st.divider()
    
    # Kombinationen berechnen
    with st.spinner("Berechne optimale Kombinationen..."):
        result = calculate_strategy_combinations(
            analyzer, metrics, target_risk, source_currency, target_currency
        )
    
    if not result['combinations']:
        st.warning("Keine geeigneten Optionskombinationen gefunden. Möglicherweise sind nicht alle benötigten Laufzeiten verfügbar.")
        return
    
    # =====================
    # BESTE KOMBINATION
    # =====================
    st.subheader("🏆 Beste Kombination")
    
    best = result['best_combination']
    fx = result['fx_rate']
    
    # Übersichtskarten
    metric_cols = st.columns(4)
    
    with metric_cols[0]:
        st.metric(
            "Anzahl Kontrakte",
            f"{best['num_contracts']}",
            help="Optimale Anzahl für Ziel-Risiko"
        )
    
    with metric_cols[1]:
        st.metric(
            f"Max. Risiko ({target_currency})",
            f"{curr_symbol}{best['max_risk_chf']:,.0f}",
            help="Maximaler Verlust bei schlechtestem Szenario"
        )
    
    with metric_cols[2]:
        div_yield = metrics.get('dividend_yield', 0)
        delta_color = "normal" if best['premium_yield'] > div_yield else "inverse"
        st.metric(
            "Prämienrendite (p.a.)",
            f"{best['premium_yield']:.1f}%",
            delta=f"{best['vs_dividend']:+.1f}% vs. Dividende",
            delta_color=delta_color
        )
    
    with metric_cols[3]:
        st.metric(
            "Kurspartizipation",
            f"{best['upside_participation']*100:.0f}%",
            help="Anteil an Kurssteigerungen"
        )
    
    # Detailansicht der Kombination
    st.markdown("#### 📋 Komponentendetails")
    
    comp_cols = st.columns(3)
    
    with comp_cols[0]:
        st.markdown("**🔵 Long Call (KAUF)**")
        lc = best['long_call']
        st.write(f"Strike: {curr_symbol}{lc['strike'] * fx:.2f}")
        st.write(f"Verfall: {lc['expiry']} ({lc['days']} Tage)")
        st.write(f"Prämie: {curr_symbol}{lc['premium'] * fx:.2f}")
        st.write(f"IV: {lc['iv']:.1f}%")
    
    with comp_cols[1]:
        st.markdown("**🔴 Short Put (VERKAUF)**")
        sp = best['short_put']
        st.write(f"Strike: {curr_symbol}{sp['strike'] * fx:.2f} ({sp['otm_pct']:.1f}% OTM)")
        st.write(f"Verfall: {sp['expiry']} ({sp['days']} Tage)")
        st.write(f"Prämie: {curr_symbol}{sp['premium'] * fx:.2f}")
        st.write(f"IV: {sp['iv']:.1f}%")
    
    with comp_cols[2]:
        st.markdown("**🟡 Hedge Put (KAUF)**")
        hp = best['hedge_put']
        st.write(f"Strike: {curr_symbol}{hp['strike'] * fx:.2f} ({hp['otm_pct']:.1f}% OTM)")
        st.write(f"Verfall: {hp['expiry']} ({hp['days']} Tage)")
        st.write(f"Kosten: {curr_symbol}{hp['premium'] * fx:.2f}")
        st.write(f"IV: {hp['iv']:.1f}%")
    
    # Netto-Position
    st.markdown("#### 💰 Netto-Position")
    
    net_cols = st.columns(3)
    
    with net_cols[0]:
        net_cost = best['net_cost']
        if net_cost > 0:
            st.error(f"Netto-Kosten: {curr_symbol}{net_cost * fx:,.2f} (Debit)")
        else:
            st.success(f"Netto-Einnahme: {curr_symbol}{abs(net_cost) * fx:,.2f} (Credit)")
    
    with net_cols[1]:
        st.info(f"Kapitalbindung: {curr_symbol}{best['capital_required_chf']:,.2f}")
    
    with net_cols[2]:
        # Kontrollierter Wert
        controlled_value = best['num_contracts'] * 100 * current_price * fx
        leverage = controlled_value / best['capital_required_chf'] if best['capital_required_chf'] > 0 else 0
        st.info(f"Kontrollierter Wert: {curr_symbol}{controlled_value:,.0f} (Hebel: {leverage:.1f}x)")
    
    st.divider()
    
    # =====================
    # WEITERE KOMBINATIONEN (VOLLSTÄNDIG)
    # =====================
    if len(result['combinations']) > 1:
        st.subheader("📊 Alternative Kombinationen")
        
        for i, combo in enumerate(result['combinations'][1:5], 2):
            with st.expander(f"**Kombination {i}** - Rendite: {combo['premium_yield']:.1f}% | Risiko: {curr_symbol}{combo['max_risk_chf']:,.0f}"):
                
                # Übersichtskarten
                alt_metric_cols = st.columns(4)
                
                with alt_metric_cols[0]:
                    st.metric("Anzahl Kontrakte", f"{combo['num_contracts']}")
                
                with alt_metric_cols[1]:
                    st.metric(f"Max. Risiko ({target_currency})", f"{curr_symbol}{combo['max_risk_chf']:,.0f}")
                
                with alt_metric_cols[2]:
                    div_yield = metrics.get('dividend_yield', 0)
                    st.metric("Prämienrendite (p.a.)", f"{combo['premium_yield']:.1f}%",
                             delta=f"{combo['vs_dividend']:+.1f}% vs. Div.")
                
                with alt_metric_cols[3]:
                    st.metric("Kurspartizipation", f"{combo['upside_participation']*100:.0f}%")
                
                # Komponenten-Details
                st.markdown("##### Komponenten")
                alt_comp_cols = st.columns(3)
                
                with alt_comp_cols[0]:
                    st.markdown("**🔵 Long Call (KAUF)**")
                    lc = combo['long_call']
                    st.write(f"Strike: {curr_symbol}{lc['strike'] * fx:.2f}")
                    st.write(f"Verfall: {lc['expiry']} ({lc['days']} Tage)")
                    st.write(f"Prämie: {curr_symbol}{lc['premium'] * fx:.2f}")
                    st.write(f"IV: {lc['iv']:.1f}%")
                
                with alt_comp_cols[1]:
                    st.markdown("**🔴 Short Put (VERKAUF)**")
                    sp = combo['short_put']
                    st.write(f"Strike: {curr_symbol}{sp['strike'] * fx:.2f} ({sp['otm_pct']:.1f}% OTM)")
                    st.write(f"Verfall: {sp['expiry']} ({sp['days']} Tage)")
                    st.write(f"Prämie: {curr_symbol}{sp['premium'] * fx:.2f}")
                    st.write(f"IV: {sp['iv']:.1f}%")
                
                with alt_comp_cols[2]:
                    st.markdown("**🟡 Hedge Put (KAUF)**")
                    hp = combo['hedge_put']
                    st.write(f"Strike: {curr_symbol}{hp['strike'] * fx:.2f} ({hp['otm_pct']:.1f}% OTM)")
                    st.write(f"Verfall: {hp['expiry']} ({hp['days']} Tage)")
                    st.write(f"Kosten: {curr_symbol}{hp['premium'] * fx:.2f}")
                    st.write(f"IV: {hp['iv']:.1f}%")
                
                # Netto-Position
                st.markdown("##### Netto-Position")
                alt_net_cols = st.columns(3)
                
                with alt_net_cols[0]:
                    net_cost = combo['net_cost']
                    if net_cost > 0:
                        st.error(f"Netto-Kosten: {curr_symbol}{net_cost * fx:,.2f}")
                    else:
                        st.success(f"Netto-Einnahme: {curr_symbol}{abs(net_cost) * fx:,.2f}")
                
                with alt_net_cols[1]:
                    st.info(f"Kapitalbindung: {curr_symbol}{combo['capital_required_chf']:,.2f}")
                
                with alt_net_cols[2]:
                    controlled = combo['num_contracts'] * 100 * current_price * fx
                    lev = controlled / combo['capital_required_chf'] if combo['capital_required_chf'] > 0 else 0
                    st.info(f"Hebel: {lev:.1f}x")
    
    st.divider()
    
    # =====================
    # KURZFRISTIGE CALL-VERKÄUFE
    # =====================
    st.subheader("🟢 Kurzfristige Call-Verkäufe (50% Abdeckung)")
    
    st.markdown("""
    Zur Generierung konstanter Renditen bei wenig volatilem Verlauf wird empfohlen, 
    ca. 50% der Basis-Kombination mit wöchentlichen Call-Verkäufen zu ergänzen.
    """)
    
    # Signale berechnen
    signals = calculate_short_call_signals(analyzer, metrics, best['num_contracts'])
    
    # Signal-Anzeige
    signal_cols = st.columns(4)
    
    with signal_cols[0]:
        macd_color = "🟢" if signals['macd_signal'] > 0.2 else ("🔴" if signals['macd_signal'] < -0.2 else "🟡")
        st.metric(
            f"{macd_color} MACD-Signal",
            f"{signals['macd_signal']:.2f}",
            help="Positiv = bearish = gut für Call-Verkauf"
        )
    
    with signal_cols[1]:
        sma_color = "🟢" if signals['sma200_signal'] > 0.2 else ("🔴" if signals['sma200_signal'] < -0.2 else "🟡")
        st.metric(
            f"{sma_color} SMA200-Signal",
            f"{signals['sma200_signal']:.2f}",
            help="Positiv = überkauft = gut für Call-Verkauf"
        )
    
    with signal_cols[2]:
        season_color = "🟢" if signals['seasonality_signal'] > 0.2 else ("🔴" if signals['seasonality_signal'] < -0.2 else "🟡")
        st.metric(
            f"{season_color} Saisonalität",
            f"{signals['seasonality_signal']:.2f}",
            help="Positiv = schwache Woche erwartet"
        )
    
    with signal_cols[3]:
        combined_color = "🟢" if signals['combined_score'] > 0.2 else ("🔴" if signals['combined_score'] < -0.2 else "🟡")
        st.metric(
            f"{combined_color} Gesamt-Score",
            f"{signals['combined_score']:.2f}",
            help="Gewichteter Durchschnitt aller Signale"
        )
    
    # Empfehlung
    st.markdown("#### 📝 Empfehlung")
    
    rec_cols = st.columns(2)
    
    with rec_cols[0]:
        rec_color = "success" if signals['recommendation'] in ['STARK VERKAUFEN', 'MODERAT VERKAUFEN'] else (
            "warning" if signals['recommendation'] == 'LEICHT VERKAUFEN' else "info"
        )
        
        if rec_color == "success":
            st.success(f"**{signals['recommendation']}**: {signals['num_calls_to_sell']} Kontrakte")
        elif rec_color == "warning":
            st.warning(f"**{signals['recommendation']}**: {signals['num_calls_to_sell']} Kontrakte")
        else:
            st.info(f"**{signals['recommendation']}**")
    
    with rec_cols[1]:
        if signals['strike_recommendation'] > 0:
            st.info(f"Strike-Empfehlung: {curr_symbol}{signals['strike_recommendation'] * fx:.2f}")
    
    # Detail-Informationen
    with st.expander("📊 Signal-Details"):
        details = signals.get('details', {})
        
        if 'macd' in details:
            st.write(f"**MACD:** {details['macd']:.4f}")
            st.write(f"**MACD Signal-Linie:** {details['macd_signal_line']:.4f}")
            st.write(f"**MACD Histogram:** {details['macd_histogram']:.4f}")
        
        if 'sma_200' in details:
            st.write(f"**SMA 200:** {curr_symbol}{details['sma_200'] * fx:.2f}")
            st.write(f"**Abstand zu SMA 200:** {details['distance_to_sma200_pct']:.2f}%")
        
        if 'current_week' in details:
            st.write(f"**Aktuelle Kalenderwoche:** {details['current_week']}")
            st.write(f"**Saisonale Ø-Rendite dieser Woche:** {details['seasonal_avg_return']:.2f}%")
            st.write(f"**Anteil positiver Wochen:** {details['seasonal_positive_pct']:.1f}%")
        
        if 'atr' in details:
            st.write(f"**ATR (14 Tage):** {curr_symbol}{details['atr'] * fx:.2f}")
    
    st.divider()
    
    # =====================
    # WECHSEL-SIGNALE
    # =====================
    st.subheader("🔄 Wechsel- und Exit-Signale")
    
    st.markdown("""
    Prognostizierte Wechselmöglichkeiten bei Kursveränderungen oder vor Optionsverfall.
    """)
    
    # Szenarien simulieren
    scenarios = [
        ("Kurs +10%", current_price * 1.10),
        ("Kurs +20%", current_price * 1.20),
        ("Kurs -10%", current_price * 0.90),
        ("Kurs -20%", current_price * 0.80),
    ]
    
    for scenario_name, scenario_price in scenarios:
        exit_signals = calculate_exit_signals(best, scenario_price, current_price)
        
        with st.expander(f"📈 Szenario: {scenario_name} → {curr_symbol}{scenario_price * fx:.2f}"):
            if exit_signals['overall_action'] == 'DRINGEND ANPASSEN':
                st.error(f"⚠️ **{exit_signals['overall_action']}**")
            elif exit_signals['overall_action'] == 'ANPASSUNG PRÜFEN':
                st.warning(f"⚡ **{exit_signals['overall_action']}**")
            else:
                st.success(f"✅ **{exit_signals['overall_action']}**")
            
            for key, label in [('long_call_exit', 'Long Call'), 
                              ('short_put_exit', 'Short Put'),
                              ('hedge_put_exit', 'Hedge Put')]:
                if exit_signals[key]:
                    sig = exit_signals[key]
                    urgency_icon = "🔴" if sig['urgency'] == 'HOCH' else ("🟡" if sig['urgency'] == 'MITTEL' else "🟢")
                    st.write(f"{urgency_icon} **{label}:** {sig['action']} - {sig['reason']}")
    
    # Zeitbasierte Warnungen
    st.markdown("#### ⏰ Zeitbasierte Warnungen")
    
    time_warnings = []
    
    if best['hedge_put']['days'] < 45:
        time_warnings.append(f"🔴 **Hedge Put** läuft in {best['hedge_put']['days']} Tagen aus - ROLLEN!")
    elif best['hedge_put']['days'] < 90:
        time_warnings.append(f"🟡 **Hedge Put** läuft in {best['hedge_put']['days']} Tagen aus - Rollen planen")
    
    if best['long_call']['days'] < 60:
        time_warnings.append(f"🔴 **Long Call** läuft in {best['long_call']['days']} Tagen aus - ROLLEN!")
    elif best['long_call']['days'] < 120:
        time_warnings.append(f"🟡 **Long Call** läuft in {best['long_call']['days']} Tagen aus - Rollen planen")
    
    if best['short_put']['days'] < 90:
        time_warnings.append(f"🟡 **Short Put** läuft in {best['short_put']['days']} Tagen aus - Rollen prüfen")
    
    if time_warnings:
        for warning in time_warnings:
            st.markdown(warning)
    else:
        st.success("✅ Keine dringenden zeitbasierten Aktionen erforderlich")
    
    st.divider()
    
    # =====================
    # BACKTEST
    # =====================
    st.subheader("📊 Backtest")
    
    st.markdown("""
    Simulation der Strategie mit historischen Kursdaten.
    - Optionen werden zum **Mittelkurs** (Mid) gekauft/verkauft
    - Der Kursverlauf basiert auf der **prozentualen Änderung** des Basiswerts
    - Kurzfristige Calls werden **wöchentlich gerollt**
    """)
    
    # Eingabefelder
    bt_col1, bt_col2, bt_col3 = st.columns(3)
    
    with bt_col1:
        # Startdatum - Default: vor 60 Tagen
        default_start = datetime.now() - timedelta(days=90)
        backtest_start = st.date_input(
            "Startdatum",
            value=default_start,
            min_value=datetime.now() - timedelta(days=730),
            max_value=datetime.now() - timedelta(days=7),
            help="Beginn des Backtest-Zeitraums"
        )
    
    with bt_col2:
        backtest_days = st.number_input(
            "Anzahl Tage",
            min_value=7,
            max_value=365,
            value=60,
            step=7,
            help="Dauer des Backtests in Tagen"
        )
    
    with bt_col3:
        st.metric(
            "Aktueller Kurs",
            f"{curr_symbol}{current_price * fx_rate:.2f}",
            help="Dieser Kurs wird als Startwert verwendet"
        )
    
    # Backtest starten
    if st.button("🔄 Backtest starten", type="primary"):
        # Konvertiere date zu datetime
        start_dt = datetime.combine(backtest_start, datetime.min.time())
        
        with st.spinner(f"Berechne Backtest ({backtest_days} Tage)..."):
            backtest_result = run_simple_backtest(
                analyzer=analyzer,
                combination=best,
                start_date=start_dt,
                num_days=backtest_days,
                current_price=current_price,
                source_currency=source_currency,
                target_currency=target_currency
            )
        
        # Ergebnisse anzeigen
        display_backtest(backtest_result, curr_symbol, target_currency)
    else:
        st.info("👆 Wähle Startdatum und Anzahl Tage, dann klicke 'Backtest starten'")


# ============================================================================
#                           HAUPTANWENDUNG
# ============================================================================

def main():
    st.title("📊 Aktienanalyse für Optionenstrategie")
    st.markdown("*Analyse-Tool für sichere Rendite zur Rentenergänzung - Version 2.8 (Echte Strikes + Börsenzeiten)*")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        
        ticker_input = st.text_input(
            "Ticker-Symbol eingeben",
            value="KO",
            help="z.B. KO für Coca-Cola, AAPL für Apple, SPY für S&P 500 ETF"
        ).upper()
        
        analyze_button = st.button("🔍 Analysieren", type="primary", use_container_width=True)
        
        st.divider()
        
        # Währungsauswahl
        st.markdown("**💱 Währung**")
        display_currency = st.selectbox(
            "Anzeigewährung",
            options=['CHF', 'USD', 'EUR'],
            index=0,  # CHF als Standard
            help="Alle Beträge werden in diese Währung umgerechnet"
        )
        
        # Wechselkurs anzeigen
        if display_currency != 'USD':
            rate = currency_converter.get_exchange_rate('USD', display_currency)
            st.caption(f"💹 1 USD = {rate:.4f} {display_currency}")
        
        st.divider()
        
        st.markdown("**Chart-Einstellungen**")
        chart_type = st.radio("Chart-Typ", ["Kerzen", "Linie"], horizontal=True)
        
        st.divider()
        
        st.markdown("**Über die Strategie**")
        st.info("""
        Diese Analyse unterstützt eine Optionenstrategie mit:
        - 🔵 Langlaufender Call Kauf (6-12 Mo)
        - 🔴 Langlaufender Put Verkauf (12-24 Mo)
        - 🟡 Sicherungs-Put Kauf (3-6 Mo)
        - 🟢 Kurzlaufender Call Verkauf (wöchentlich)
        
        **Ziel:** Hebel ~7x für sichere Zusatzrente
        """)
    
    # Hauptbereich
    if analyze_button or 'analyzer' in st.session_state:
        
        if analyze_button:
            with st.spinner(f"Lade Daten für {ticker_input}..."):
                st.session_state['analyzer'] = StockAnalyzer(ticker_input)
                st.session_state['metrics'] = st.session_state['analyzer'].get_key_metrics()
                st.session_state['thumbs'] = st.session_state['analyzer'].calculate_three_thumbs_rule()
        
        analyzer = st.session_state['analyzer']
        metrics = st.session_state['metrics']
        thumbs = st.session_state['thumbs']
        
        # Quellwährung aus Ticker-Info
        source_currency = metrics.get('currency', 'USD')
        
        # Währungssymbol für Anzeige
        curr_symbol = 'CHF ' if display_currency == 'CHF' else ('€' if display_currency == 'EUR' else '$')
        
        # Konvertierter Preis
        current_price_converted = currency_converter.convert(
            metrics.get('current_price', 0), 
            source_currency, 
            display_currency
        )
        
        # Header mit Basisinfos
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Ticker", analyzer.ticker)
        with col2:
            st.metric(f"Aktueller Kurs ({display_currency})", f"{curr_symbol}{current_price_converted:,.2f}")
        with col3:
            previous_close = metrics.get('previous_close', 0)
            if previous_close and previous_close > 0:
                change = ((metrics.get('current_price', 0) / previous_close) - 1) * 100
                st.metric("Tagesänderung", f"{change:+.2f}%")
            else:
                st.metric("Tagesänderung", "N/A")
        with col4:
            st.metric("3-Daumen", f"{thumbs['total_thumbs']}/3 👍")
        
        st.divider()
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📁 Holdings",
            "📊 Kennzahlen",
            "📈 Chart 5 Jahre",
            "📉 Chart 1 Jahr",
            "🗓️ Saisonalität",
            "⚡ Optionsanalyse",
            "🎯 Strategie-Builder"
        ])
        
        # TAB 1: Holdings
        with tab1:
            st.header("📁 Holdings / Bestandteile")
            
            if analyzer.is_etf():
                st.info(f"{analyzer.ticker} ist ein ETF")
                holdings = analyzer.get_holdings()
                
                if holdings is not None and not holdings.empty:
                    st.dataframe(holdings, use_container_width=True)
                else:
                    st.warning("Keine detaillierten Holdings-Daten verfügbar.")
                    
                    st.markdown("**Verfügbare ETF-Informationen:**")
                    etf_info = {
                        'Kategorie': analyzer.info.get('category', 'N/A'),
                        'Fondstyp': analyzer.info.get('fundFamily', 'N/A'),
                        'Gesamtvermögen': format_number(analyzer.info.get('totalAssets', 0), 'currency'),
                        'Kostenquote': f"{analyzer.info.get('expenseRatio', 0)*100:.2f}%" if analyzer.info.get('expenseRatio') else 'N/A'
                    }
                    for key, value in etf_info.items():
                        st.write(f"**{key}:** {value}")
            else:
                st.info(f"{analyzer.ticker} ist eine Einzelaktie - keine Holdings verfügbar")
                
                st.markdown("**Unternehmensinformationen:**")
                company_info = {
                    'Name': metrics.get('name', 'N/A'),
                    'Sektor': metrics.get('sector', 'N/A'),
                    'Industrie': metrics.get('industry', 'N/A'),
                    'Börse': metrics.get('exchange', 'N/A'),
                    'Währung': metrics.get('currency', 'N/A'),
                    'Website': metrics.get('website', 'N/A')
                }
                for key, value in company_info.items():
                    if key == 'Website' and value and value != 'N/A':
                        st.write(f"**{key}:** [{value}]({value})")
                    else:
                        st.write(f"**{key}:** {value}")
                
                description = analyzer.info.get('longBusinessSummary', '')
                if description:
                    with st.expander("📝 Unternehmensbeschreibung"):
                        st.write(description)
        
        # TAB 2: Kennzahlen
        with tab2:
            st.header(f"📊 Wesentliche Kennzahlen (in {display_currency})")
            
            # 3-Daumen-Regel
            display_three_thumbs(thumbs)
            
            st.divider()
            
            # Wichtige Termine
            st.subheader("📅 Wichtige Termine")
            
            dates_info = analyzer.get_upcoming_dates()
            
            term_cols = st.columns(2)
            with term_cols[0]:
                ex_div_str = dates_info['ex_dividend_date_str']
                if dates_info['ex_dividend_estimated']:
                    st.warning(f"📅 Nächster Ex-Dividenden-Tag: **{ex_div_str}**")
                    if dates_info['estimated_dividend']:
                        div_converted = currency_converter.convert(dates_info['estimated_dividend'], source_currency, display_currency)
                        st.write(f"   Geschätzte Dividende: {curr_symbol}{div_converted:.4f}")
                else:
                    st.info(f"📅 Nächster Ex-Dividenden-Tag: **{ex_div_str}**")
            
            with term_cols[1]:
                earnings_str = dates_info['earnings_date_str']
                if dates_info['earnings_estimated']:
                    st.warning(f"📊 Nächster Earnings-Termin: **{earnings_str}**")
                else:
                    st.info(f"📊 Nächster Earnings-Termin: **{earnings_str}**")
            
            st.divider()
            
            # Hauptkennzahlen
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("💰 Bewertung")
                st.metric("Marktkapitalisierung", format_number(metrics.get('market_cap', 0), 'currency', source_currency, display_currency))
                st.metric("Umsatz (TTM)", format_number(metrics.get('revenue', 0), 'currency', source_currency, display_currency))
                st.metric("P/E Ratio", f"{metrics.get('pe_ratio', 0):.2f}")
                st.metric("Forward P/E", f"{metrics.get('forward_pe', 0):.2f}")
                st.metric("Price to Book", f"{metrics.get('price_to_book', 0):.2f}")
            
            with col2:
                st.subheader("💵 Cash Flow")
                st.metric("Free Cash Flow", format_number(metrics.get('free_cash_flow', 0), 'currency', source_currency, display_currency))
                st.metric("FCF Yield", f"{metrics.get('fcf_yield', 0):.2f}%")
                st.metric("Price to FCF", f"{metrics.get('price_to_fcf', 0):.2f}")
                st.metric("Operating CF", format_number(metrics.get('operating_cash_flow', 0), 'currency', source_currency, display_currency))
                st.metric("EBITDA", format_number(metrics.get('ebitda', 0), 'currency', source_currency, display_currency))
            
            with col3:
                st.subheader("📈 Dividende")
                div_yield = metrics.get('dividend_yield', 0)
                st.metric("Dividendenrendite", f"{div_yield:.2f}%")
                div_rate_converted = currency_converter.convert(metrics.get('dividend_rate', 0), source_currency, display_currency)
                st.metric(f"Dividende (p.a.)", f"{curr_symbol}{div_rate_converted:.2f}")
                payout = metrics.get('payout_ratio', 0) or 0
                st.metric("Ausschüttungsquote", f"{payout*100:.2f}%")
            
            st.divider()
            
            # Dividenden-Historie 10 Jahre
            display_dividend_history(analyzer, source_currency, display_currency, curr_symbol)
            
            st.divider()
            
            # Risiko
            st.subheader("⚠️ Risikokennzahlen")
            risk_cols = st.columns(4)
            
            with risk_cols[0]:
                beta = metrics.get('beta', 0)
                beta_color = "normal" if 0.8 <= beta <= 1.2 else "inverse"
                st.metric("Beta", f"{beta:.2f}", 
                         delta="Marktkonform" if 0.8 <= beta <= 1.2 else "Abweichend",
                         delta_color=beta_color)
            
            with risk_cols[1]:
                st.metric("Debt/Equity", f"{metrics.get('debt_to_equity', 0):.2f}")
            
            with risk_cols[2]:
                st.metric("Current Ratio", f"{metrics.get('current_ratio', 0):.2f}")
            
            with risk_cols[3]:
                st.metric("Quick Ratio", f"{metrics.get('quick_ratio', 0):.2f}")
        
        # TAB 3: Chart 5 Jahre
        with tab3:
            st.header(f"📈 Kursverlauf 5 Jahre")
            
            # Wechselkurs für Charts
            chart_fx_rate = currency_converter.get_exchange_rate(source_currency, display_currency)
            
            # Info über Dual-Währungsanzeige
            if display_currency != source_currency:
                st.info(f"""📊 **Historische Währungsumrechnung aktiv**
                - Preise werden mit **tagesaktuellem {source_currency}/{display_currency}-Kurs** des jeweiligen Tages umgerechnet
                - Linke Y-Achse: **{display_currency}** | Rechte Y-Achse: **{source_currency}** (gepunktet)
                - Zusätzlich: Wechselkursverlauf im 2. Chart""")
            
            with st.spinner("Lade 5-Jahres-Daten und Wechselkurse..."):
                history_5y = analyzer.get_history("5y")
                
                if not history_5y.empty:
                    fig_5y = create_price_chart(
                        history_5y, 
                        f"{analyzer.ticker} - 5 Jahre",
                        show_candles=(chart_type == "Kerzen"),
                        fx_rate=chart_fx_rate,
                        currency_symbol=curr_symbol,
                        source_currency=source_currency,
                        target_currency=display_currency
                    )
                    st.plotly_chart(fig_5y, use_container_width=True)
                else:
                    st.error("Keine historischen Daten verfügbar")
        
        # TAB 4: Chart 1 Jahr
        with tab4:
            st.header(f"📉 Kursverlauf 1 Jahr")
            
            # Info über Dual-Währungsanzeige
            if display_currency != source_currency:
                st.info(f"""📊 **Historische Währungsumrechnung aktiv**
                - Preise werden mit **tagesaktuellem {source_currency}/{display_currency}-Kurs** umgerechnet
                - Wechselkursverlauf im 2. Chart""")
            
            with st.spinner("Lade 1-Jahres-Daten und Wechselkurse..."):
                history_1y = analyzer.get_history("1y")
                
                if not history_1y.empty:
                    fig_1y = create_price_chart(
                        history_1y,
                        f"{analyzer.ticker} - 1 Jahr",
                        show_candles=(chart_type == "Kerzen"),
                        fx_rate=chart_fx_rate,
                        currency_symbol=curr_symbol,
                        source_currency=source_currency,
                        target_currency=display_currency
                    )
                    st.plotly_chart(fig_1y, use_container_width=True)
                    
                    # Performance-Statistiken
                    st.subheader("📊 Performance-Statistiken (1 Jahr)")
                    perf_cols = st.columns(4)
                    
                    returns = history_1y['Close'].pct_change().dropna()
                    
                    with perf_cols[0]:
                        total_return = ((history_1y['Close'].iloc[-1] / history_1y['Close'].iloc[0]) - 1) * 100
                        st.metric("Gesamtrendite", f"{total_return:+.2f}%")
                    
                    with perf_cols[1]:
                        volatility = returns.std() * np.sqrt(252) * 100
                        st.metric("Volatilität (ann.)", f"{volatility:.2f}%")
                    
                    with perf_cols[2]:
                        max_dd = ((history_1y['Close'] / history_1y['Close'].cummax()) - 1).min() * 100
                        st.metric("Max. Drawdown", f"{max_dd:.2f}%")
                    
                    with perf_cols[3]:
                        sharpe = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
                        st.metric("Sharpe Ratio", f"{sharpe:.2f}")
                else:
                    st.error("Keine historischen Daten verfügbar")
        
        # TAB 5: Saisonalität
        with tab5:
            st.header("🗓️ Saisonaler Verlauf")
            
            with st.spinner("Berechne saisonale Muster..."):
                seasonal_data = analyzer.get_seasonal_data()
                
                if not seasonal_data.empty:
                    fig_seasonal = create_seasonal_chart(seasonal_data, analyzer.ticker)
                    st.plotly_chart(fig_seasonal, use_container_width=True)
                    
                    st.subheader("📊 Statistische Auswertung")
                    
                    stat_cols = st.columns(2)
                    
                    with stat_cols[0]:
                        st.markdown("**🟢 Beste Wochen (Top 5)**")
                        best_weeks = seasonal_data.nlargest(5, 'Avg_Return_Pct')[['Week', 'Avg_Return_Pct', 'Positive_Pct']]
                        best_weeks.columns = ['KW', 'Ø Rendite %', 'Positiv %']
                        st.dataframe(best_weeks, use_container_width=True, hide_index=True)
                    
                    with stat_cols[1]:
                        st.markdown("**🔴 Schlechteste Wochen (Top 5)**")
                        worst_weeks = seasonal_data.nsmallest(5, 'Avg_Return_Pct')[['Week', 'Avg_Return_Pct', 'Positive_Pct']]
                        worst_weeks.columns = ['KW', 'Ø Rendite %', 'Positiv %']
                        st.dataframe(worst_weeks, use_container_width=True, hide_index=True)
                    
                    current_week = datetime.now().isocalendar().week
                    current_week_data = seasonal_data[seasonal_data['Week'] == current_week]
                    if not current_week_data.empty:
                        st.info(f"""
                        📅 **Aktuelle Kalenderwoche {current_week}:**
                        - Durchschnittliche Rendite: {current_week_data['Avg_Return_Pct'].values[0]:.2f}%
                        - Anteil positiver Jahre: {current_week_data['Positive_Pct'].values[0]:.0f}%
                        """)
                else:
                    st.warning("Nicht genügend Daten für saisonale Analyse")
        
        # TAB 6: Optionsanalyse
        with tab6:
            st.header(f"⚡ Optionsanalyse (in {display_currency})")
            display_options_analysis(analyzer, metrics, source_currency, display_currency, curr_symbol)
        
        # TAB 7: Strategie-Builder
        with tab7:
            display_strategy_builder(analyzer, metrics, source_currency, display_currency, curr_symbol)
        
        # Zusammenfassung
        st.divider()
        
        if st.button("📄 Zusammenfassung erstellen", type="secondary"):
            summary = generate_summary(analyzer, metrics, thumbs)
            
            st.text_area("Zusammenfassung (kopieren oder speichern)", summary, height=400)
            
            st.download_button(
                label="💾 Als Textdatei herunterladen",
                data=summary,
                file_name=f"{analyzer.ticker}_analyse_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )


if __name__ == "__main__":
    main()
