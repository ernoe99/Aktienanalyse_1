"""
Aktienanalyse-Tool für Optionenstrategie zur Rentenergänzung
============================================================
Streamlit-basierte Anwendung zur Analyse von Aktien und ETFs
mit Fokus auf sichere Rendite durch Optionsstrategien.

Autor: Claude
Version: 2.1 - Mit CHF Währungsumrechnung
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
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
    .positive { color: #00c853; }
    .negative { color: #ff1744; }
    .neutral { color: #ffc107; }
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
    }
    .strategy-comparison {
        display: flex;
        gap: 20px;
    }
</style>
""", unsafe_allow_html=True)


class CurrencyConverter:
    """Klasse für Währungsumrechnung"""
    
    def __init__(self):
        self.rates = {}
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
            
            # Erste 5 Handelstage des Jahres
            first_5_days = ytd_data.head(5)
            if len(first_5_days) >= 2:
                first_5_days_return = ((first_5_days['Close'].iloc[-1] / first_5_days['Close'].iloc[0]) - 1) * 100
                first_5_positive = first_5_days_return > 0
                result['details']['first_5_days_return'] = first_5_days_return
                
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
    Erstellt den Preischart mit allen Indikatoren und Dual-Währungsanzeige.
    
    Args:
        df: DataFrame mit OHLCV-Daten
        title: Chart-Titel
        show_candles: True für Kerzen, False für Linie
        fx_rate: Wechselkurs für Währungsumrechnung
        currency_symbol: Währungssymbol für Zielwährung
        source_currency: Quellwährung (z.B. 'USD')
        target_currency: Zielwährung (z.B. 'CHF')
    """
    
    # Kopie erstellen
    df = df.copy()
    
    # Original-Preise speichern (für sekundäre Y-Achse)
    df['Close_Original'] = df['Close']
    df['High_Original'] = df['High']
    df['Low_Original'] = df['Low']
    
    # Preise umrechnen für primäre Anzeige
    df['Open'] = df['Open'] * fx_rate
    df['High'] = df['High'] * fx_rate
    df['Low'] = df['Low'] * fx_rate
    df['Close'] = df['Close'] * fx_rate
    
    # Indikatoren auf umgerechneten Preisen berechnen
    analyzer_temp = StockAnalyzer.__new__(StockAnalyzer)
    df = analyzer_temp.calculate_moving_averages(df)
    df = analyzer_temp.calculate_bollinger_bands(df)
    df = analyzer_temp.calculate_macd(df)
    df = analyzer_temp.calculate_rsi(df)
    
    # Prüfen ob Währungsumrechnung aktiv ist
    show_dual_currency = (fx_rate != 1.0 and source_currency != target_currency)
    
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(title, 'Volumen', 'MACD', 'RSI'),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}], 
               [{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    if show_candles:
        # Hauptchart in Zielwährung (CHF)
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
    
    # Sekundäre Y-Achse mit Originalwährung (USD) - nur als Linie
    if show_dual_currency:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['Close_Original'],
                mode='lines',
                name=f'Kurs ({source_currency})',
                line=dict(color='rgba(100,100,100,0.4)', width=1, dash='dot'),
                hovertemplate=f'{source_currency} %{{y:.2f}}<extra></extra>'
            ),
            row=1, col=1, secondary_y=True
        )
    
    # Bollinger Bänder (in Zielwährung)
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
    
    # SMAs (in Zielwährung)
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
    
    # Volumen
    colors = ['#00c853' if df['Close'].iloc[i] >= df['Open'].iloc[i] 
              else '#ff1744' for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], name='Volumen', marker_color=colors,
               showlegend=False),
        row=2, col=1
    )
    
    # MACD (in Zielwährung)
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD',
                   line=dict(color='#2196f3', width=1.5), showlegend=False),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal',
                   line=dict(color='#ff9800', width=1.5), showlegend=False),
        row=3, col=1
    )
    colors_macd = ['#00c853' if val >= 0 else '#ff1744' for val in df['MACD_Histogram']]
    fig.add_trace(
        go.Bar(x=df.index, y=df['MACD_Histogram'], name='Histogram', marker_color=colors_macd,
               showlegend=False),
        row=3, col=1
    )
    
    # RSI (dimensionslos)
    fig.add_trace(
        go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI',
                   line=dict(color='#9c27b0', width=1.5), showlegend=False),
        row=4, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.1)", 
                  line_width=0, row=4, col=1)
    
    fig.update_layout(
        height=900,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        template='plotly_white'
    )
    
    # Y-Achsen Beschriftung
    target_label = target_currency if target_currency else currency_symbol.strip()
    fig.update_yaxes(title_text=f"Preis ({target_label})", row=1, col=1, secondary_y=False,
                     tickformat=".2f", tickprefix=currency_symbol)
    
    if show_dual_currency:
        fig.update_yaxes(title_text=f"Preis ({source_currency})", row=1, col=1, secondary_y=True,
                         tickformat=".2f", tickprefix="$", showgrid=False)
    
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    fig.update_yaxes(title_text=f"MACD", row=3, col=1)
    fig.update_yaxes(title_text="RSI", row=4, col=1)
    
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
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb1_emoji} Daumen 1</h3>
            <p><b>{thumbs_result['thumb1']['description']}</b></p>
            <p class="{thumb1_color}">
                {thumbs_result['details'].get('price_vs_sma200', 0):.2f}% über/unter SMA200
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        thumb2_emoji = "👍" if thumbs_result['thumb2']['value'] else "👎"
        thumb2_color = "positive" if thumbs_result['thumb2']['value'] else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb2_emoji} Daumen 2</h3>
            <p><b>{thumbs_result['thumb2']['description']}</b></p>
            <p class="{thumb2_color}">
                YTD: {thumbs_result['details'].get('ytd_return', 0):.2f}%
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        thumb3_emoji = "👍" if thumbs_result['thumb3']['value'] else "👎"
        thumb3_color = "positive" if thumbs_result['thumb3']['value'] else "negative"
        year_type = "Ungerade" if thumbs_result['details'].get('is_odd_year', True) else "Gerade"
        st.markdown(f"""
        <div class="metric-card">
            <h3>{thumb3_emoji} Daumen 3</h3>
            <p><b>{thumbs_result['thumb3']['description']}</b></p>
            <p>Jahr: {year_type}</p>
            <p class="{thumb3_color}">
                Erste 5 Tage: {thumbs_result['details'].get('first_5_days_return', 0):.2f}%
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        total = thumbs_result['total_thumbs']
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
#                           HAUPTANWENDUNG
# ============================================================================

def main():
    st.title("📊 Aktienanalyse für Optionenstrategie")
    st.markdown("*Analyse-Tool für sichere Rendite zur Rentenergänzung - Version 2.1 (CHF)*")
    
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
            change = ((metrics.get('current_price', 0) / metrics.get('previous_close', 1)) - 1) * 100
            st.metric("Tagesänderung", f"{change:+.2f}%")
        with col4:
            st.metric("3-Daumen", f"{thumbs['total_thumbs']}/3 👍")
        
        st.divider()
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📁 Holdings",
            "📊 Kennzahlen",
            "📈 Chart 5 Jahre",
            "📉 Chart 1 Jahr",
            "🗓️ Saisonalität",
            "⚡ Optionsanalyse"
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
                st.info(f"📊 Chart zeigt Preise in **{display_currency}** (linke Y-Achse) und **{source_currency}** (rechte Y-Achse, gepunktet)")
            
            with st.spinner("Lade 5-Jahres-Daten..."):
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
                st.info(f"📊 Chart zeigt Preise in **{display_currency}** (linke Y-Achse) und **{source_currency}** (rechte Y-Achse, gepunktet)")
            
            with st.spinner("Lade 1-Jahres-Daten..."):
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
