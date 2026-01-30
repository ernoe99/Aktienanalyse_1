"""
Aktienanalyse-Tool für Optionenstrategie zur Rentenergänzung
============================================================
Streamlit-basierte Anwendung zur Analyse von Aktien und ETFs
mit Fokus auf sichere Rendite durch Optionsstrategien.

Autor: Claude
Version: 3.0 - Variable Strike-Prozente + Strategie-Vergleich
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
    .strategy-a {
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
    }
    .strategy-b {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
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
        """
        if from_currency == to_currency:
            return pd.DataFrame()
        
        cache_key = f"{from_currency}_{to_currency}_{period}"
        
        if cache_key in self.historical_rates:
            return self.historical_rates[cache_key]
        
        try:
            ticker = f"{from_currency}{to_currency}=X"
            fx = yf.Ticker(ticker)
            history = fx.history(period=period)
            
            if not history.empty:
                rates_df = history[['Close']].copy()
                rates_df.columns = ['Rate']
                
                if rates_df.index.tz is not None:
                    rates_df.index = rates_df.index.tz_localize(None)
                
                self.historical_rates[cache_key] = rates_df
                return rates_df
            
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
        
        return pd.DataFrame()
    
    def convert_historical(self, df: pd.DataFrame, price_columns: list,
                          from_currency: str, to_currency: str,
                          period: str = "5y") -> pd.DataFrame:
        """
        Konvertiert historische Preisspalten mit historischen Wechselkursen.
        """
        if from_currency == to_currency:
            return df
        
        result_df = df.copy()
        
        fx_rates = self.get_historical_rates(from_currency, to_currency, period)
        
        if fx_rates.empty:
            current_rate = self.get_exchange_rate(from_currency, to_currency)
            for col in price_columns:
                if col in result_df.columns:
                    result_df[col] = result_df[col] * current_rate
            return result_df
        
        if result_df.index.tz is not None:
            result_df.index = result_df.index.tz_localize(None)
        
        aligned_rates = fx_rates.reindex(result_df.index, method='ffill')
        aligned_rates = aligned_rates.fillna(method='bfill')
        
        if aligned_rates['Rate'].isna().any():
            current_rate = self.get_exchange_rate(from_currency, to_currency)
            aligned_rates['Rate'] = aligned_rates['Rate'].fillna(current_rate)
        
        for col in price_columns:
            if col in result_df.columns:
                result_df[col] = result_df[col] * aligned_rates['Rate']
        
        return result_df
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Konvertiert einen Betrag"""
        if from_currency == to_currency:
            return amount
        rate = self.get_exchange_rate(from_currency, to_currency)
        return amount * rate


# Globale Converter-Instanz
currency_converter = CurrencyConverter()


class StockAnalyzer:
    """Hauptklasse für die Aktienanalyse"""
    
    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        self.info = self._get_info_safe()
        
    def _get_info_safe(self) -> dict:
        """Holt Info mit Fallback"""
        try:
            info = self.stock.info
            return info if info else {}
        except:
            return {}
    
    def is_etf(self) -> bool:
        """Prüft ob es sich um einen ETF handelt"""
        quote_type = self.info.get('quoteType', '')
        return quote_type == 'ETF'
    
    def get_holdings(self) -> pd.DataFrame:
        """Holt Holdings für ETFs"""
        try:
            if hasattr(self.stock, 'funds_data'):
                funds = self.stock.funds_data
                if hasattr(funds, 'top_holdings'):
                    holdings = funds.top_holdings
                    if holdings is not None and not holdings.empty:
                        return holdings
        except:
            pass
        return pd.DataFrame()
    
    def get_history(self, period: str = "5y") -> pd.DataFrame:
        """Holt historische Kursdaten"""
        try:
            history = self.stock.history(period=period)
            if history.index.tz is not None:
                history.index = history.index.tz_localize(None)
            return history
        except:
            return pd.DataFrame()
    
    def get_key_metrics(self) -> dict:
        """Sammelt wesentliche Kennzahlen"""
        info = self.info
        
        metrics = {
            'name': info.get('longName') or info.get('shortName', self.ticker),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'exchange': info.get('exchange', 'N/A'),
            'currency': info.get('currency', 'USD'),
            'website': info.get('website', 'N/A'),
            'current_price': info.get('currentPrice') or info.get('regularMarketPrice', 0),
            'previous_close': info.get('previousClose', 0),
            '52w_high': info.get('fiftyTwoWeekHigh', 0),
            '52w_low': info.get('fiftyTwoWeekLow', 0),
            'market_cap': info.get('marketCap', 0),
            'revenue': info.get('totalRevenue', 0),
            'pe_ratio': info.get('trailingPE', 0) or 0,
            'forward_pe': info.get('forwardPE', 0) or 0,
            'price_to_book': info.get('priceToBook', 0) or 0,
            'dividend_yield': (info.get('dividendYield', 0) or 0) * 100,
            'dividend_rate': info.get('dividendRate', 0) or 0,
            'payout_ratio': info.get('payoutRatio', 0) or 0,
            'beta': info.get('beta', 0) or 0,
            'debt_to_equity': info.get('debtToEquity', 0) or 0,
            'current_ratio': info.get('currentRatio', 0) or 0,
            'quick_ratio': info.get('quickRatio', 0) or 0,
            'free_cash_flow': info.get('freeCashflow', 0) or 0,
            'operating_cash_flow': info.get('operatingCashflow', 0) or 0,
            'ebitda': info.get('ebitda', 0) or 0,
        }
        
        if metrics['current_price'] > 0 and metrics['free_cash_flow'] > 0:
            shares = info.get('sharesOutstanding', 0)
            if shares > 0:
                fcf_per_share = metrics['free_cash_flow'] / shares
                metrics['fcf_yield'] = (fcf_per_share / metrics['current_price']) * 100
                metrics['price_to_fcf'] = metrics['current_price'] / fcf_per_share
            else:
                metrics['fcf_yield'] = 0
                metrics['price_to_fcf'] = 0
        else:
            metrics['fcf_yield'] = 0
            metrics['price_to_fcf'] = 0
        
        return metrics
    
    def calculate_moving_averages(self, data: pd.DataFrame) -> pd.DataFrame:
        """Berechnet gleitende Durchschnitte"""
        if 'Close' not in data.columns:
            return data
        
        data['SMA_50'] = data['Close'].rolling(window=50).mean()
        data['SMA_200'] = data['Close'].rolling(window=200).mean()
        
        data['EMA_12'] = data['Close'].ewm(span=12, adjust=False).mean()
        data['EMA_26'] = data['Close'].ewm(span=26, adjust=False).mean()
        
        return data
    
    def calculate_macd(self, data: pd.DataFrame) -> pd.DataFrame:
        """Berechnet MACD-Indikatoren"""
        if 'Close' not in data.columns:
            return data
        
        data['EMA_12'] = data['Close'].ewm(span=12, adjust=False).mean()
        data['EMA_26'] = data['Close'].ewm(span=26, adjust=False).mean()
        data['MACD'] = data['EMA_12'] - data['EMA_26']
        data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['MACD_Histogram'] = data['MACD'] - data['MACD_Signal']
        
        return data
    
    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Berechnet Average True Range"""
        if len(data) < period:
            data['ATR'] = 0
            return data
        
        high = data['High']
        low = data['Low']
        close = data['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['ATR'] = tr.rolling(window=period).mean()
        
        return data
    
    def calculate_three_thumbs_rule(self) -> dict:
        """
        Berechnet die 3-Daumen-Regel:
        1. Kurs über 200-Tage-SMA
        2. YTD-Performance positiv
        3. Jahresregel: Wenn erste 5 Tage positiv → Jahr positiv
        """
        result = {
            'thumb1': {'value': False, 'description': 'Kurs über 200-Tage-SMA'},
            'thumb2': {'value': False, 'description': 'YTD-Performance positiv'},
            'thumb3': {'value': False, 'description': 'Jahresregel erfüllt'},
            'total_thumbs': 0,
            'details': {}
        }
        
        history = self.get_history("2y")
        if history.empty:
            return result
        
        if history.index.tz is not None:
            history.index = history.index.tz_localize(None)
        
        history = self.calculate_moving_averages(history)
        
        current_price = history['Close'].iloc[-1]
        
        # Daumen 1: Kurs über 200-Tage-SMA
        if 'SMA_200' in history.columns and not pd.isna(history['SMA_200'].iloc[-1]):
            sma_200 = history['SMA_200'].iloc[-1]
            result['thumb1']['value'] = current_price > sma_200
            result['details']['sma_200'] = sma_200
            result['details']['price_vs_sma200'] = ((current_price / sma_200) - 1) * 100
        
        # Daumen 2: YTD-Performance positiv
        current_year = datetime.now().year
        ytd_start = datetime(current_year, 1, 1)
        ytd_data = history[history.index >= ytd_start]
        
        if len(ytd_data) >= 2:
            ytd_return = (ytd_data['Close'].iloc[-1] / ytd_data['Close'].iloc[0] - 1) * 100
            result['thumb2']['value'] = ytd_return > 0
            result['details']['ytd_return'] = ytd_return
        
        # Daumen 3: Erste 5 Tage des Jahres
        first_5_days = history[(history.index >= ytd_start)].head(5)
        
        if len(first_5_days) >= 5:
            first_5_return = (first_5_days['Close'].iloc[-1] / first_5_days['Close'].iloc[0] - 1) * 100
            result['thumb3']['value'] = first_5_return > 0
            result['details']['first_5_days_return'] = first_5_return
            
            if first_5_return > 0:
                result['thumb3']['description'] = f'Erste 5 Tage positiv ({first_5_return:+.2f}%) → Gutes Jahr erwartet'
            else:
                result['thumb3']['description'] = f'Erste 5 Tage negativ ({first_5_return:+.2f}%) → Vorsicht geboten'
        
        # Gesamtzahl Daumen
        result['total_thumbs'] = sum([
            result['thumb1']['value'],
            result['thumb2']['value'],
            result['thumb3']['value']
        ])
        
        return result
    
    def get_seasonal_data(self) -> pd.DataFrame:
        """Berechnet saisonale Muster auf Wochenbasis"""
        history = self.get_history("10y")
        
        if history.empty:
            return pd.DataFrame()
        
        if history.index.tz is not None:
            history.index = history.index.tz_localize(None)
        
        history['Week'] = history.index.isocalendar().week
        history['Year'] = history.index.year
        history['Weekly_Return'] = history['Close'].pct_change(5) * 100
        
        weekly_data = history.groupby(['Year', 'Week']).agg({
            'Weekly_Return': 'last',
            'Close': 'last'
        }).reset_index()
        
        seasonal = weekly_data.groupby('Week').agg({
            'Weekly_Return': ['mean', 'std', lambda x: (x > 0).sum() / len(x) * 100]
        }).reset_index()
        
        seasonal.columns = ['Week', 'Avg_Return_Pct', 'Std_Dev', 'Positive_Pct']
        
        return seasonal
    
    def get_options_chain(self) -> dict:
        """Holt die Optionskette"""
        try:
            expirations = self.stock.options
            if not expirations:
                return None
            
            exp_date = expirations[0]
            opt_chain = self.stock.option_chain(exp_date)
            
            return {
                'expiration': exp_date,
                'calls': opt_chain.calls,
                'puts': opt_chain.puts
            }
        except:
            return None
    
    def get_all_options_expirations(self) -> list:
        """Holt alle verfügbaren Verfalltermine"""
        try:
            return list(self.stock.options)
        except:
            return []
    
    def get_options_for_expiration(self, expiration: str) -> dict:
        """Holt Optionskette für spezifischen Verfall"""
        try:
            opt_chain = self.stock.option_chain(expiration)
            return {
                'expiration': expiration,
                'calls': opt_chain.calls,
                'puts': opt_chain.puts
            }
        except:
            return None
    
    def get_strategy_options(self) -> dict:
        """
        Holt Optionen für die 4-Komponenten-Strategie
        """
        expirations = self.get_all_options_expirations()
        
        if not expirations:
            return {}
        
        today = datetime.now()
        
        def parse_exp(exp_str):
            try:
                return datetime.strptime(exp_str, '%Y-%m-%d')
            except:
                return None
        
        exp_dates = [(exp, parse_exp(exp)) for exp in expirations]
        exp_dates = [(e, d) for e, d in exp_dates if d is not None]
        
        def find_option_in_range(min_days, max_days):
            for exp, date in exp_dates:
                days = (date - today).days
                if min_days <= days <= max_days:
                    chain = self.get_options_for_expiration(exp)
                    if chain:
                        return {
                            'expiration': exp,
                            'days': days,
                            'options': chain
                        }
            return None
        
        result = {
            'long_call_buy': None,
            'long_put_sell': None,
            'hedge_put_buy': None,
            'short_call_sell': None
        }
        
        # 1. Long Call Kauf (6-12 Monate)
        for exp, date in exp_dates:
            days = (date - today).days
            if 180 <= days <= 365:
                chain = self.get_options_for_expiration(exp)
                if chain and not chain['calls'].empty:
                    result['long_call_buy'] = {
                        'expiration': exp,
                        'days': days,
                        'options': chain['calls']
                    }
                    break
        
        # 2. Long Put Verkauf (12-24 Monate)
        for exp, date in exp_dates:
            days = (date - today).days
            if 365 <= days <= 730:
                chain = self.get_options_for_expiration(exp)
                if chain and not chain['puts'].empty:
                    result['long_put_sell'] = {
                        'expiration': exp,
                        'days': days,
                        'options': chain['puts']
                    }
                    break
        
        # 3. Hedge Put Kauf (3-6 Monate)
        for exp, date in exp_dates:
            days = (date - today).days
            if 90 <= days <= 180:
                chain = self.get_options_for_expiration(exp)
                if chain and not chain['puts'].empty:
                    result['hedge_put_buy'] = {
                        'expiration': exp,
                        'days': days,
                        'options': chain['puts']
                    }
                    break
        
        # 4. Kurzfristiger Call Verkauf (1-2 Wochen)
        for exp, date in exp_dates:
            days = (date - today).days
            if 3 <= days <= 14:
                chain = self.get_options_for_expiration(exp)
                if chain and not chain['calls'].empty:
                    result['short_call_sell'] = {
                        'expiration': exp,
                        'days': days,
                        'options': chain['calls']
                    }
                    break
        
        return result
    
    def get_upcoming_dates(self) -> dict:
        """Holt wichtige anstehende Termine"""
        result = {
            'ex_dividend_date': None,
            'ex_dividend_date_str': 'Unbekannt',
            'ex_dividend_estimated': False,
            'estimated_dividend': None,
            'earnings_date': None,
            'earnings_date_str': 'Unbekannt',
            'earnings_estimated': False
        }
        
        try:
            ex_div = self.info.get('exDividendDate')
            if ex_div:
                if isinstance(ex_div, (int, float)):
                    ex_div_date = datetime.fromtimestamp(ex_div)
                    result['ex_dividend_date'] = ex_div_date
                    result['ex_dividend_date_str'] = ex_div_date.strftime('%d.%m.%Y')
        except:
            pass
        
        try:
            cal = self.stock.calendar
            if cal is not None and not cal.empty:
                if 'Earnings Date' in cal.columns:
                    earnings = cal['Earnings Date'].iloc[0]
                    if pd.notna(earnings):
                        result['earnings_date'] = earnings
                        result['earnings_date_str'] = earnings.strftime('%d.%m.%Y')
        except:
            pass
        
        return result


# ============================================================================
#                       HELPER FUNCTIONS
# ============================================================================


def format_number(value, format_type='number', source_currency='USD', target_currency='CHF'):
    """Formatiert große Zahlen lesbar"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    
    if format_type == 'currency' and source_currency != target_currency:
        value = currency_converter.convert(value, source_currency, target_currency)
    
    abs_value = abs(value)
    
    if abs_value >= 1e12:
        return f"{value/1e12:.2f}T"
    elif abs_value >= 1e9:
        return f"{value/1e9:.2f}Mrd"
    elif abs_value >= 1e6:
        return f"{value/1e6:.2f}Mio"
    elif abs_value >= 1e3:
        return f"{value/1e3:.2f}K"
    else:
        return f"{value:.2f}"


def display_three_thumbs(thumbs: dict):
    """Zeigt die 3-Daumen-Regel an"""
    st.subheader("👍 3-Daumen-Regel")
    
    total = thumbs['total_thumbs']
    
    if total == 3:
        st.success(f"**{total}/3 Daumen** - SEHR GUT: Alle Kriterien erfüllt!")
    elif total == 2:
        st.warning(f"**{total}/3 Daumen** - GUT: Zwei von drei Kriterien erfüllt")
    else:
        st.error(f"**{total}/3 Daumen** - VORSICHT: Weniger als zwei Kriterien erfüllt")
    
    cols = st.columns(3)
    
    for i, (key, thumb) in enumerate([
        ('thumb1', thumbs['thumb1']),
        ('thumb2', thumbs['thumb2']),
        ('thumb3', thumbs['thumb3'])
    ]):
        with cols[i]:
            if thumb['value']:
                st.markdown(f"### ✅ Daumen {i+1}")
            else:
                st.markdown(f"### ❌ Daumen {i+1}")
            
            st.write(thumb['description'])
            
            if 'details' in thumbs:
                if key == 'thumb1' and 'price_vs_sma200' in thumbs['details']:
                    st.caption(f"Abstand: {thumbs['details']['price_vs_sma200']:+.2f}%")
                elif key == 'thumb2' and 'ytd_return' in thumbs['details']:
                    st.caption(f"YTD: {thumbs['details']['ytd_return']:+.2f}%")


def create_price_chart(data: pd.DataFrame, title: str, show_candles: bool = True,
                       fx_rate: float = 1.0, currency_symbol: str = '$',
                       source_currency: str = 'USD', target_currency: str = 'CHF'):
    """Erstellt einen Preischart mit Dual-Währung bei Bedarf"""
    
    if target_currency != source_currency:
        data_converted = currency_converter.convert_historical(
            data.copy(), 
            ['Open', 'High', 'Low', 'Close'],
            source_currency,
            target_currency,
            period="5y"
        )
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.75, 0.25],
            subplot_titles=(f'{title} ({target_currency})', f'{source_currency}/{target_currency} Wechselkurs')
        )
        
        if show_candles:
            fig.add_trace(go.Candlestick(
                x=data_converted.index,
                open=data_converted['Open'],
                high=data_converted['High'],
                low=data_converted['Low'],
                close=data_converted['Close'],
                name=f'Kurs ({target_currency})',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=data_converted.index,
                y=data_converted['Close'],
                name=f'Kurs ({target_currency})',
                line=dict(color='#2196f3', width=2)
            ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['Close'],
            name=f'Kurs ({source_currency})',
            line=dict(color='gray', width=1, dash='dot'),
            yaxis='y3',
            opacity=0.5
        ), row=1, col=1)
        
        fx_history = currency_converter.get_historical_rates(source_currency, target_currency, "5y")
        if not fx_history.empty:
            fx_aligned = fx_history.reindex(data.index, method='ffill')
            fig.add_trace(go.Scatter(
                x=fx_aligned.index,
                y=fx_aligned['Rate'],
                name=f'{source_currency}/{target_currency}',
                line=dict(color='#ff9800', width=2),
                fill='tozeroy',
                fillcolor='rgba(255,152,0,0.1)'
            ), row=2, col=1)
        
        fig.update_layout(
            height=600,
            template='plotly_white',
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis=dict(title=target_currency, side='left'),
            yaxis3=dict(title=source_currency, side='right', overlaying='y', showgrid=False),
            yaxis2=dict(title='Rate')
        )
        
    else:
        fig = go.Figure()
        
        if show_candles:
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                name='Kurs',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ))
        else:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['Close'],
                name='Kurs',
                line=dict(color='#2196f3', width=2)
            ))
        
        fig.update_layout(
            title=title,
            height=500,
            template='plotly_white',
            xaxis_rangeslider_visible=False,
            yaxis_title=currency_symbol
        )
    
    return fig


def create_seasonal_chart(seasonal_data: pd.DataFrame, ticker: str):
    """Erstellt einen Saisonalitäts-Chart"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=('Durchschnittliche Wochenrendite (%)', 'Anteil positiver Wochen (%)')
    )
    
    colors = ['#26a69a' if x > 0 else '#ef5350' for x in seasonal_data['Avg_Return_Pct']]
    
    fig.add_trace(go.Bar(
        x=seasonal_data['Week'],
        y=seasonal_data['Avg_Return_Pct'],
        name='Ø Rendite',
        marker_color=colors
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(
        x=seasonal_data['Week'],
        y=seasonal_data['Positive_Pct'],
        name='Positiv %',
        marker_color='#2196f3'
    ), row=2, col=1)
    
    fig.update_layout(
        title=f'Saisonaler Verlauf {ticker} (10 Jahre)',
        height=600,
        template='plotly_white',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    fig.update_xaxes(title_text="Kalenderwoche", row=2, col=1)
    
    return fig


# ============================================================================
#                   STRIKE-FINDING FUNCTIONS (NEU/ERWEITERT)
# ============================================================================


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
        if price < 20:
            if direction == 'above':
                return round((price + 0.25) * 2) / 2
            else:
                return round((price - 0.25) * 2) / 2
        elif price < 50:
            if direction == 'above':
                return round(price + 0.5)
            else:
                return round(price - 0.5)
        else:
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


def find_absolute_nearest_strike(target_price: float, available_strikes: list) -> float:
    """
    Findet den ABSOLUT nächsten verfügbaren Strike (oben oder unten).
    
    Args:
        target_price: Zielpreis basierend auf Prozent-Offset
        available_strikes: Liste verfügbarer Strikes
        
    Returns:
        Der Strike, der dem Zielpreis am nächsten liegt
    """
    if not available_strikes:
        # Fallback: auf 0.50 / 1.00 / 5.00 runden je nach Preisniveau
        if target_price < 20:
            return round(target_price * 2) / 2  # 0.50 Schritte
        elif target_price < 50:
            return round(target_price)  # 1.00 Schritte
        else:
            return round(target_price / 5) * 5  # 5.00 Schritte
    
    # Finde den Strike mit der kleinsten absoluten Differenz
    differences = [(abs(s - target_price), s) for s in available_strikes]
    nearest = min(differences, key=lambda x: x[0])[1]
    
    return nearest


def get_strike_from_percent(current_price: float, percent_offset: float, 
                           available_strikes: list) -> tuple:
    """
    Berechnet den Strike basierend auf Prozent-Offset und findet den nächsten verfügbaren.
    
    Args:
        current_price: Aktueller Aktienkurs
        percent_offset: Prozent-Offset (positiv = OTM für Calls, negativ = ITM)
        available_strikes: Liste verfügbarer Strikes
        
    Returns:
        (strike, actual_percent): Gefundener Strike und tatsächlicher Prozent-Abstand
    """
    # Zielpreis berechnen
    target_price = current_price * (1 + percent_offset / 100)
    
    # Nächsten Strike finden
    strike = find_absolute_nearest_strike(target_price, available_strikes)
    
    # Tatsächlichen Prozent-Abstand berechnen
    actual_percent = ((strike / current_price) - 1) * 100
    
    return strike, actual_percent


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


def is_market_open() -> tuple:
    """Prüft ob die US-Börse gerade geöffnet ist."""
    try:
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        weekday = now_et.weekday()
        hour = now_et.hour
        minute = now_et.minute
        
        if weekday >= 5:
            return False, f"⚠️ Börse geschlossen (Wochenende). Optionspreise können ungenau sein."
        
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
        return True, strike
    
    if strike in available_strikes:
        return True, strike
    
    differences = [(abs(s - strike), s) for s in available_strikes]
    nearest = min(differences, key=lambda x: x[0])[1]
    
    return False, nearest


# ============================================================================
#                       BACKTEST FUNKTIONEN
# ============================================================================


def run_simple_backtest(analyzer: StockAnalyzer, combination: dict,
                        start_date: datetime, num_days: int,
                        current_price: float,
                        source_currency: str = 'USD',
                        target_currency: str = 'CHF',
                        min_call_premium: float = 0.05) -> dict:
    """
    Backtest mit echten Strikes aus der Optionskette und Black-Scholes Bewertung.
    
    Args:
        analyzer: StockAnalyzer instance
        combination: Strategie-Kombination
        start_date: Startdatum
        num_days: Anzahl Tage
        current_price: Aktueller Kurs
        source_currency: Quellwährung
        target_currency: Zielwährung
        min_call_premium: Mindest-Prämie für wöchentliche Calls
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
        
        # Skalierung für Kursverlauf
        hist_start = bt_data['Close'].iloc[0]
        scale = current_price / hist_start
        
        available_strikes = get_available_strikes(analyzer)
        
        n = combination['num_contracts']
        long_call = combination['long_call']
        short_put = combination['short_put']
        hedge_put = combination['hedge_put']
        
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
        first_price = bt_data['Close'].iloc[0] * scale
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
        skipped_calls = 0  # Zähler für übersprungene Calls wegen zu niedriger Prämie
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
            
            # Wöchentlicher Call-Verfall
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
            
            # Saisonalitäts-Score
            score = 0.2
            if not seasonal.empty:
                wk = seasonal[seasonal['Week'] == week]
                if not wk.empty:
                    avg_ret = wk['Avg_Return_Pct'].iloc[0]
                    if avg_ret < -0.3:
                        score += 0.3
                    elif avg_ret > 0.3:
                        score -= 0.2
            
            # Neuer wöchentlicher Call-Verkauf
            if new_week:
                target = max(1, n // 2)
                if score >= 0.2:
                    target_strike = price * 1.015
                    potential_strike = find_nearest_strike(target_strike, available_strikes, 'above')
                    
                    short_call_T = short_call_days / 365
                    potential_premium = black_scholes(price, potential_strike, short_call_T, risk_free_rate, current_vol, 'call')
                    
                    # PRÄMIEN-CHECK: Nur verkaufen wenn Prämie >= min_call_premium
                    if potential_premium >= min_call_premium:
                        short_call_qty = target
                        short_call_strike = potential_strike
                        short_call_premium = potential_premium
                        
                        trades.append({'date': dt, 'day': i + 1, 'action': 'VERKAUF', 'type': 'Short Call (Wöchentlich)',
                            'strike': short_call_strike, 'expiry_days': short_call_days,
                            'premium': short_call_premium, 'bs_value': short_call_premium, 'volatility': current_vol,
                            'quantity': short_call_qty, 'total': short_call_premium * 100 * short_call_qty,
                            'price': price})
                    else:
                        # Prämie zu niedrig - nicht verkaufen
                        short_call_qty = 0
                        skipped_calls += 1
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
            'weekly_calls_income': total_call_income,
            'skipped_calls': skipped_calls
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
            'volatility_30d': final_vol, 'skipped_calls': skipped_calls
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


def display_backtest_comparison(result_a: dict, result_b: dict, 
                                curr_symbol: str, target_currency: str):
    """
    Zeigt Backtest-Vergleich für beide Strategien nebeneinander.
    """
    
    st.markdown("## 📊 Backtest-Vergleich")
    
    # Prüfe ob beide erfolgreich
    if not result_a['success'] and not result_b['success']:
        st.error("Beide Backtests fehlgeschlagen")
        return
    
    # Gemeinsame Infos
    if result_a['success']:
        s = result_a['summary']
        st.info(f"**Zeitraum:** {s['start_date']} bis {s['end_date']} ({s['num_days']} Handelstage)")
    elif result_b['success']:
        s = result_b['summary']
        st.info(f"**Zeitraum:** {s['start_date']} bis {s['end_date']} ({s['num_days']} Handelstage)")
    
    st.divider()
    
    # ==================
    # VERGLEICHSTABELLE
    # ==================
    st.subheader("📈 Ergebnis-Vergleich")
    
    def get_summary_value(result, key, default=0):
        if result['success']:
            return result['summary'].get(key, default)
        return default
    
    fx_a = get_summary_value(result_a, 'fx', 1.0)
    fx_b = get_summary_value(result_b, 'fx', 1.0)
    
    comparison_data = {
        'Metrik': [
            f'Startkurs ({target_currency})',
            f'Endkurs ({target_currency})',
            'Kursänderung',
            f'Investment ({target_currency})',
            f'Endwert ({target_currency})',
            f'Netto-Ergebnis ({target_currency})',
            'Strategie-Rendite',
            'Aktie Buy&Hold',
            'Outperformance',
            'Call-Einnahmen',
            'Übersprungene Calls',
            '30-Tage Volatilität'
        ],
        '🅰️ Strategie A': [
            f"{curr_symbol}{get_summary_value(result_a, 'start_price')*fx_a:.2f}" if result_a['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_a, 'end_price')*fx_a:.2f}" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'price_change_pct'):+.1f}%" if result_a['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_a, 'investment')*fx_a:,.0f}" if result_a['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_a, 'final_value')*fx_a:,.0f}" if result_a['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_a, 'net_result')*fx_a:+,.0f}" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'strategy_pct'):+.1f}%" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'stock_pct'):+.1f}%" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'outperformance'):+.1f}%" if result_a['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_a, 'call_income')*fx_a:,.0f}" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'skipped_calls', 0)}" if result_a['success'] else "❌",
            f"{get_summary_value(result_a, 'volatility_30d', 0)*100:.1f}%" if result_a['success'] else "❌"
        ],
        '🅱️ Strategie B': [
            f"{curr_symbol}{get_summary_value(result_b, 'start_price')*fx_b:.2f}" if result_b['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_b, 'end_price')*fx_b:.2f}" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'price_change_pct'):+.1f}%" if result_b['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_b, 'investment')*fx_b:,.0f}" if result_b['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_b, 'final_value')*fx_b:,.0f}" if result_b['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_b, 'net_result')*fx_b:+,.0f}" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'strategy_pct'):+.1f}%" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'stock_pct'):+.1f}%" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'outperformance'):+.1f}%" if result_b['success'] else "❌",
            f"{curr_symbol}{get_summary_value(result_b, 'call_income')*fx_b:,.0f}" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'skipped_calls', 0)}" if result_b['success'] else "❌",
            f"{get_summary_value(result_b, 'volatility_30d', 0)*100:.1f}%" if result_b['success'] else "❌"
        ]
    }
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
    
    # ==================
    # GEWINNER
    # ==================
    if result_a['success'] and result_b['success']:
        strat_a = result_a['summary']['strategy_pct']
        strat_b = result_b['summary']['strategy_pct']
        
        if strat_a > strat_b:
            winner = "A"
            diff = strat_a - strat_b
            st.success(f"🏆 **Strategie A gewinnt** mit {diff:.1f}% höherer Rendite!")
        elif strat_b > strat_a:
            winner = "B"
            diff = strat_b - strat_a
            st.success(f"🏆 **Strategie B gewinnt** mit {diff:.1f}% höherer Rendite!")
        else:
            st.info("🤝 **Unentschieden** - Beide Strategien gleich performt")
    
    st.divider()
    
    # ==================
    # VERGLEICHS-CHART
    # ==================
    st.subheader("📈 Rendite-Verlauf Vergleich")
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
        row_heights=[0.6, 0.4],
        subplot_titles=('Strategie-Rendite (%)', 'Kurs-Verlauf'))
    
    # Strategie A
    if result_a['success'] and result_a['data']:
        df_a = pd.DataFrame(result_a['data'])
        fx_a = result_a['summary']['fx']
        
        fig.add_trace(go.Scatter(
            x=df_a['date'], y=df_a['strategy_pct'], 
            name='🅰️ Strategie A', 
            line=dict(color='#4caf50', width=2)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df_a['date'], y=df_a['price']*fx_a, 
            name='Kurs', 
            line=dict(color='#2196f3', width=2)
        ), row=2, col=1)
    
    # Strategie B
    if result_b['success'] and result_b['data']:
        df_b = pd.DataFrame(result_b['data'])
        fx_b = result_b['summary']['fx']
        
        fig.add_trace(go.Scatter(
            x=df_b['date'], y=df_b['strategy_pct'], 
            name='🅱️ Strategie B', 
            line=dict(color='#ff9800', width=2)
        ), row=1, col=1)
    
    # Aktie (nur einmal)
    if result_a['success'] and result_a['data']:
        df_a = pd.DataFrame(result_a['data'])
        fig.add_trace(go.Scatter(
            x=df_a['date'], y=df_a['stock_pct'], 
            name='Aktie B&H', 
            line=dict(color='gray', width=2, dash='dash')
        ), row=1, col=1)
    
    fig.add_hline(y=0, line_color="black", row=1, col=1)
    
    fig.update_layout(
        height=600, 
        template='plotly_white', 
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode='x unified'
    )
    fig.update_yaxes(title_text="%", row=1, col=1)
    fig.update_yaxes(title_text=target_currency, row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ==================
    # DETAIL-TABS
    # ==================
    st.subheader("📋 Detail-Ansichten")
    
    detail_tab_a, detail_tab_b = st.tabs(["🅰️ Details Strategie A", "🅱️ Details Strategie B"])
    
    with detail_tab_a:
        if result_a['success']:
            display_single_backtest(result_a, curr_symbol, target_currency, "A")
        else:
            st.error(f"Fehler: {result_a.get('error', 'Unbekannt')}")
    
    with detail_tab_b:
        if result_b['success']:
            display_single_backtest(result_b, curr_symbol, target_currency, "B")
        else:
            st.error(f"Fehler: {result_b.get('error', 'Unbekannt')}")


def display_single_backtest(result: dict, curr_symbol: str, target_currency: str, label: str):
    """Zeigt Details eines einzelnen Backtests."""
    
    s = result['summary']
    data = result['data']
    trades = result.get('trades', [])
    final_val = result.get('final_valuation', {})
    warnings = result.get('warnings', [])
    fx = s.get('fx', 1.0)
    
    # Warnungen
    if warnings:
        for w in warnings:
            st.warning(f"⚠️ {w}")
    
    # Übersprungene Calls
    skipped = s.get('skipped_calls', 0)
    if skipped > 0:
        st.info(f"ℹ️ {skipped} wöchentliche Calls wurden wegen zu niedriger Prämie übersprungen")
    
    # Metriken
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strategie", f"{s['strategy_pct']:+.1f}%")
    c2.metric("Aktie", f"{s['stock_pct']:+.1f}%")
    c3.metric("Outperformance", f"{s['outperformance']:+.1f}%")
    c4.metric("Call-Einnahmen", f"{curr_symbol}{s['call_income']*fx:,.0f}")
    
    # Schlussbewertung
    st.markdown("#### 📐 Schlussbewertung (Black-Scholes)")
    
    if final_val:
        val_cols = st.columns(3)
        
        with val_cols[0]:
            lc = final_val.get('long_call', {})
            st.markdown("**🔵 Long Call**")
            st.write(f"Strike: {curr_symbol}{lc.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {lc.get('days_left', 0)} Tage")
            st.success(f"Wert: {curr_symbol}{lc.get('total_value', 0)*fx:,.0f}")
        
        with val_cols[1]:
            sp = final_val.get('short_put', {})
            st.markdown("**🔴 Short Put**")
            st.write(f"Strike: {curr_symbol}{sp.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {sp.get('days_left', 0)} Tage")
            st.error(f"Rückkauf: {curr_symbol}{sp.get('total_liability', 0)*fx:,.0f}")
        
        with val_cols[2]:
            hp = final_val.get('hedge_put', {})
            st.markdown("**🟡 Hedge Put**")
            st.write(f"Strike: {curr_symbol}{hp.get('strike', 0)*fx:.2f}")
            st.write(f"Restlaufzeit: {hp.get('days_left', 0)} Tage")
            st.success(f"Wert: {curr_symbol}{hp.get('total_value', 0)*fx:,.0f}")
    
    # Trades
    with st.expander("📝 Alle Transaktionen"):
        if trades:
            trade_table = []
            for t in trades:
                trade_table.append({
                    'Datum': t['date'].strftime('%Y-%m-%d'),
                    'Aktion': t['action'],
                    'Typ': t['type'],
                    f'Strike': f"{curr_symbol}{t['strike']*fx:.2f}",
                    f'Prämie': f"{curr_symbol}{t['premium']*fx:.2f}",
                    'Anz.': t['quantity'],
                    f'Gesamt': f"{curr_symbol}{t['total']*fx:+,.0f}"
                })
            st.dataframe(pd.DataFrame(trade_table), use_container_width=True, hide_index=True)
    
    # Tägliche Werte
    with st.expander("📋 Tägliche Werte"):
        tbl = [{'Datum': d['date'].strftime('%Y-%m-%d'),
            f'Kurs': f"{curr_symbol}{d['price']*fx:.2f}",
            'Änderung': f"{d['pct_change']:+.1f}%",
            'Call aktiv': '✓' if d.get('call_active') else '-',
            'Strategie': f"{d['strategy_pct']:+.1f}%", 
            'Aktie': f"{d['stock_pct']:+.1f}%"
        } for d in data]
        st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)


# ============================================================================
#                   CUSTOM STRATEGY CALCULATION (NEU)
# ============================================================================


def calculate_custom_strategy(analyzer: StockAnalyzer, metrics: dict,
                             strike_settings: dict,
                             target_risk: float = 5000,
                             source_currency: str = 'USD',
                             target_currency: str = 'CHF') -> dict:
    """
    Berechnet eine Strategie mit benutzerdefinierten Strike-Prozenten.
    
    Args:
        analyzer: StockAnalyzer instance
        metrics: Kennzahlen des Underlyings
        strike_settings: Dict mit Prozent-Einstellungen:
            - long_call_pct: z.B. 0 für ATM, -5 für 5% ITM, 5 für 5% OTM
            - short_put_pct: z.B. -15 für 15% OTM (unter Kurs)
            - hedge_put_pct: z.B. -25 für 25% OTM
        target_risk: Ziel-Risiko in Zielwährung
        source_currency: Quellwährung
        target_currency: Zielwährung
        
    Returns:
        Dict mit Strategie-Details
    """
    result = {
        'success': False,
        'combination': None,
        'warnings': [],
        'fx_rate': 1.0
    }
    
    current_price = metrics.get('current_price', 0)
    if current_price <= 0:
        result['warnings'].append("Kein aktueller Kurs verfügbar")
        return result
    
    fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    result['fx_rate'] = fx_rate
    
    # Verfügbare Strikes holen
    available_strikes = get_available_strikes(analyzer)
    if not available_strikes:
        result['warnings'].append("Keine Strikes aus Optionskette verfügbar - verwende Fallback")
    
    # Optionsketten holen
    strategy_options = analyzer.get_strategy_options()
    
    long_call_opts = strategy_options.get('long_call_buy', {})
    short_put_opts = strategy_options.get('long_put_sell', {})
    hedge_put_opts = strategy_options.get('hedge_put_buy', {})
    
    if not all([long_call_opts.get('options') is not None,
                short_put_opts.get('options') is not None,
                hedge_put_opts.get('options') is not None]):
        result['warnings'].append("Nicht alle Optionslaufzeiten verfügbar")
        return result
    
    # Strikes basierend auf Prozent-Einstellungen berechnen
    long_call_pct = strike_settings.get('long_call_pct', 0)
    short_put_pct = strike_settings.get('short_put_pct', -15)
    hedge_put_pct = strike_settings.get('hedge_put_pct', -25)
    
    # Long Call Strike
    call_target = current_price * (1 + long_call_pct / 100)
    call_strike = find_absolute_nearest_strike(call_target, available_strikes)
    call_actual_pct = ((call_strike / current_price) - 1) * 100
    
    # Short Put Strike
    put_target = current_price * (1 + short_put_pct / 100)
    put_strike = find_absolute_nearest_strike(put_target, available_strikes)
    put_actual_pct = ((put_strike / current_price) - 1) * 100
    
    # Hedge Put Strike
    hedge_target = current_price * (1 + hedge_put_pct / 100)
    hedge_strike = find_absolute_nearest_strike(hedge_target, available_strikes)
    hedge_actual_pct = ((hedge_strike / current_price) - 1) * 100
    
    # Optionen mit diesen Strikes suchen
    long_calls = long_call_opts['options']
    short_puts = short_put_opts['options']
    hedge_puts = hedge_put_opts['options']
    
    # Nächste passende Option finden
    def find_option_for_strike(options_df, target_strike, option_type='call'):
        """Findet die Option für den gegebenen Strike oder die nächste verfügbare"""
        if target_strike in options_df['strike'].values:
            return options_df[options_df['strike'] == target_strike].iloc[0]
        
        # Nächsten verfügbaren Strike finden
        strikes_in_chain = sorted(options_df['strike'].unique())
        nearest = find_absolute_nearest_strike(target_strike, strikes_in_chain)
        
        if nearest in options_df['strike'].values:
            return options_df[options_df['strike'] == nearest].iloc[0]
        
        return None
    
    call_option = find_option_for_strike(long_calls, call_strike, 'call')
    put_option = find_option_for_strike(short_puts, put_strike, 'put')
    hedge_option = find_option_for_strike(hedge_puts, hedge_strike, 'put')
    
    if call_option is None or put_option is None or hedge_option is None:
        result['warnings'].append("Nicht alle benötigten Strikes verfügbar")
        return result
    
    # Werte aus Optionen extrahieren
    call_strike = call_option['strike']
    call_ask = call_option['ask']
    call_iv = call_option.get('impliedVolatility', 0.25) * 100
    
    put_strike = put_option['strike']
    put_bid = put_option['bid']
    put_iv = put_option.get('impliedVolatility', 0.25) * 100
    
    hedge_strike = hedge_option['strike']
    hedge_ask = hedge_option['ask']
    hedge_iv = hedge_option.get('impliedVolatility', 0.30) * 100
    
    # Kosten berechnen
    call_cost = call_ask * 100
    put_income = put_bid * 100
    hedge_cost = hedge_ask * 100
    
    net_cost = call_cost - put_income + hedge_cost
    
    # Risiko berechnen
    max_risk_per_contract = (put_strike - hedge_strike) * 100 + max(0, net_cost)
    
    if max_risk_per_contract <= 0:
        max_risk_per_contract = abs(net_cost) if net_cost < 0 else call_cost
    
    # Anzahl Kontrakte
    target_risk_usd = target_risk / fx_rate
    num_contracts = max(1, int(target_risk_usd / max_risk_per_contract))
    
    actual_risk = max_risk_per_contract * num_contracts
    
    # Prämienrendite
    net_premium = put_bid - hedge_ask
    capital_required = call_cost + hedge_cost
    
    days_to_expiry = min(long_call_opts.get('days', 365), short_put_opts.get('days', 365))
    annual_factor = 365 / max(days_to_expiry, 30)
    
    if capital_required > 0:
        premium_yield = (net_premium * 100 / capital_required) * annual_factor
    else:
        premium_yield = 0
    
    # Delta-Approximation
    call_delta = 0.5 + 0.5 * (1 - call_strike / current_price) if call_strike <= current_price else 0.5 - 0.3 * (call_strike / current_price - 1)
    call_delta = max(0.3, min(0.8, call_delta))
    
    # Dividendenrendite
    div_yield = metrics.get('dividend_yield', 0)
    
    combination = {
        'long_call': {
            'strike': call_strike,
            'strike_pct': call_actual_pct,
            'target_pct': long_call_pct,
            'expiry': long_call_opts.get('expiration', 'N/A'),
            'days': long_call_opts.get('days', 0),
            'premium': call_ask,
            'iv': call_iv,
            'delta': call_delta
        },
        'short_put': {
            'strike': put_strike,
            'strike_pct': put_actual_pct,
            'target_pct': short_put_pct,
            'expiry': short_put_opts.get('expiration', 'N/A'),
            'days': short_put_opts.get('days', 0),
            'premium': put_bid,
            'iv': put_iv,
            'otm_pct': abs(put_actual_pct)
        },
        'hedge_put': {
            'strike': hedge_strike,
            'strike_pct': hedge_actual_pct,
            'target_pct': hedge_put_pct,
            'expiry': hedge_put_opts.get('expiration', 'N/A'),
            'days': hedge_put_opts.get('days', 0),
            'premium': hedge_ask,
            'iv': hedge_iv,
            'otm_pct': abs(hedge_actual_pct)
        },
        'num_contracts': num_contracts,
        'net_cost': net_cost * num_contracts,
        'max_risk': actual_risk,
        'max_risk_chf': actual_risk * fx_rate,
        'premium_yield': premium_yield,
        'vs_dividend': premium_yield - div_yield,
        'capital_required': capital_required * num_contracts,
        'capital_required_chf': capital_required * num_contracts * fx_rate,
        'upside_participation': call_delta
    }
    
    result['success'] = True
    result['combination'] = combination
    
    return result


def calculate_short_call_signals(analyzer: StockAnalyzer, metrics: dict,
                                 num_base_contracts: int = 1,
                                 min_premium: float = 0.05) -> dict:
    """
    Berechnet Empfehlungen für kurzfristige Call-Verkäufe.
    
    Args:
        analyzer: StockAnalyzer instance
        metrics: Kennzahlen
        num_base_contracts: Basis-Anzahl Kontrakte
        min_premium: Mindest-Prämie (Standard $0.05) - darunter kein Verkauf
        
    Returns:
        Dict mit Signalen und Empfehlungen
    """
    signals = {
        'macd_signal': 0,
        'sma200_signal': 0,
        'seasonality_signal': 0,
        'combined_score': 0,
        'recommendation': '',
        'num_calls_to_sell': 0,
        'strike_recommendation': 0,
        'expected_premium': 0,
        'premium_too_low': False,
        'details': {}
    }
    
    current_price = metrics.get('current_price', 0)
    if current_price <= 0:
        return signals
    
    history = analyzer.get_history("1y")
    if history.empty:
        return signals
    
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)
    
    history = analyzer.calculate_macd(history)
    history = analyzer.calculate_moving_averages(history)
    history = analyzer.calculate_atr(history)
    
    # 1. MACD-Signal
    if 'MACD' in history.columns and 'MACD_Signal' in history.columns:
        macd = history['MACD'].iloc[-1]
        macd_signal = history['MACD_Signal'].iloc[-1]
        macd_histogram = history['MACD_Histogram'].iloc[-1] if 'MACD_Histogram' in history.columns else macd - macd_signal
        
        if macd < macd_signal:
            signals['macd_signal'] = min(1.0, abs(macd_histogram) / (current_price * 0.01))
        else:
            signals['macd_signal'] = -min(1.0, abs(macd_histogram) / (current_price * 0.01))
        
        signals['details']['macd'] = macd
        signals['details']['macd_signal_line'] = macd_signal
        signals['details']['macd_histogram'] = macd_histogram
    
    # 2. SMA200-Signal
    if 'SMA_200' in history.columns:
        sma_200 = history['SMA_200'].iloc[-1]
        distance_pct = (current_price - sma_200) / sma_200 * 100
        
        if distance_pct > 5:
            signals['sma200_signal'] = min(1.0, (distance_pct - 5) / 10)
        elif distance_pct < -5:
            signals['sma200_signal'] = -min(1.0, abs(distance_pct + 5) / 10)
        else:
            signals['sma200_signal'] = 0
        
        signals['details']['sma_200'] = sma_200
        signals['details']['distance_to_sma200_pct'] = distance_pct
    
    # 3. Saisonalität
    seasonal_data = analyzer.get_seasonal_data()
    if not seasonal_data.empty:
        current_week = datetime.now().isocalendar()[1]
        
        if current_week in seasonal_data['Week'].values:
            week_data = seasonal_data[seasonal_data['Week'] == current_week].iloc[0]
            avg_return = week_data['Avg_Return_Pct']
            positive_pct = week_data['Positive_Pct']
            
            if avg_return < -0.5:
                signals['seasonality_signal'] = min(1.0, abs(avg_return) / 2)
            elif avg_return > 0.5:
                signals['seasonality_signal'] = -min(1.0, avg_return / 2)
            else:
                signals['seasonality_signal'] = 0
            
            signals['details']['current_week'] = current_week
            signals['details']['seasonal_avg_return'] = avg_return
            signals['details']['seasonal_positive_pct'] = positive_pct
    
    # Kombinierter Score
    weights = {'macd': 0.4, 'sma200': 0.35, 'seasonality': 0.25}
    signals['combined_score'] = (
        signals['macd_signal'] * weights['macd'] +
        signals['sma200_signal'] * weights['sma200'] +
        signals['seasonality_signal'] * weights['seasonality']
    )
    
    # Strike und Prämie berechnen
    base_contracts = num_base_contracts
    target_50_pct = max(1, int(base_contracts * 0.5))
    
    if 'ATR' in history.columns:
        atr = history['ATR'].iloc[-1]
        
        if signals['combined_score'] >= 0.5:
            strike_offset = 1.0 * atr
        elif signals['combined_score'] >= 0.2:
            strike_offset = 1.5 * atr
        else:
            strike_offset = 2.0 * atr
        
        strike_rec = current_price + strike_offset
        signals['strike_recommendation'] = strike_rec
        signals['details']['atr'] = atr
        
        # Erwartete Prämie mit Black-Scholes schätzen
        volatility = calculate_historical_volatility(history['Close'], 30)
        expected_premium = black_scholes(
            current_price, strike_rec, 7/365, 0.04, volatility, 'call'
        )
        signals['expected_premium'] = expected_premium
        
        # Prämien-Check
        if expected_premium < min_premium:
            signals['premium_too_low'] = True
            signals['recommendation'] = f'NICHT VERKAUFEN (Prämie ${expected_premium:.2f} < ${min_premium:.2f})'
            signals['num_calls_to_sell'] = 0
        elif signals['combined_score'] >= 0.5:
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
    
    return signals


# ============================================================================
#              STRATEGY BUILDER WITH COMPARISON (NEUER DOPPEL-TAB)
# ============================================================================


def display_strategy_builder_with_comparison(analyzer: StockAnalyzer, metrics: dict,
                                             source_currency: str, target_currency: str,
                                             curr_symbol: str):
    """
    Zeigt den Strategie-Builder mit zwei Tabs für Strategievergleich.
    """
    
    st.header("🎯 Strategie-Builder mit Vergleich")
    
    st.markdown("""
    <div class="strategy-box">
    <h4>📊 Strategie-Vergleich</h4>
    <p>Erstelle zwei Strategien mit unterschiedlichen Strike-Einstellungen und vergleiche sie direkt.</p>
    <p><b>NEU:</b> Strike-Level in % eingeben (auch negative für ITM) - der nächste verfügbare Strike wird automatisch gewählt.</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_price = metrics.get('current_price', 0)
    fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    
    # Börsenzeiten-Warnung
    market_open, market_msg = is_market_open()
    if not market_open:
        st.warning(market_msg)
    
    st.divider()
    
    # Zwei Spalten für Strategien A und B
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("### 🅰️ Strategie A")
        st.markdown('<div class="strategy-a">', unsafe_allow_html=True)
        
        target_risk_a = st.number_input(
            f"Ziel-Risiko ({target_currency})",
            min_value=1000,
            max_value=50000,
            value=5000,
            step=1000,
            key="risk_a"
        )
        
        st.markdown("**Strike-Einstellungen (% vom aktuellen Kurs)**")
        st.caption(f"Aktueller Kurs: {curr_symbol}{current_price * fx_rate:.2f}")
        
        long_call_pct_a = st.slider(
            "Long Call Strike %",
            min_value=-20.0,
            max_value=20.0,
            value=0.0,
            step=0.5,
            help="0% = ATM, negativ = ITM, positiv = OTM",
            key="call_a"
        )
        
        short_put_pct_a = st.slider(
            "Short Put Strike %",
            min_value=-40.0,
            max_value=5.0,
            value=-15.0,
            step=0.5,
            help="Typisch: -10% bis -20% (OTM)",
            key="put_a"
        )
        
        hedge_put_pct_a = st.slider(
            "Hedge Put Strike %",
            min_value=-50.0,
            max_value=-5.0,
            value=-25.0,
            step=0.5,
            help="Tiefer als Short Put für Absicherung",
            key="hedge_a"
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_b:
        st.markdown("### 🅱️ Strategie B")
        st.markdown('<div class="strategy-b">', unsafe_allow_html=True)
        
        target_risk_b = st.number_input(
            f"Ziel-Risiko ({target_currency})",
            min_value=1000,
            max_value=50000,
            value=5000,
            step=1000,
            key="risk_b"
        )
        
        st.markdown("**Strike-Einstellungen (% vom aktuellen Kurs)**")
        st.caption(f"Aktueller Kurs: {curr_symbol}{current_price * fx_rate:.2f}")
        
        long_call_pct_b = st.slider(
            "Long Call Strike %",
            min_value=-20.0,
            max_value=20.0,
            value=-5.0,
            step=0.5,
            help="0% = ATM, negativ = ITM, positiv = OTM",
            key="call_b"
        )
        
        short_put_pct_b = st.slider(
            "Short Put Strike %",
            min_value=-40.0,
            max_value=5.0,
            value=-10.0,
            step=0.5,
            help="Typisch: -10% bis -20% (OTM)",
            key="put_b"
        )
        
        hedge_put_pct_b = st.slider(
            "Hedge Put Strike %",
            min_value=-50.0,
            max_value=-5.0,
            value=-20.0,
            step=0.5,
            help="Tiefer als Short Put für Absicherung",
            key="hedge_b"
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Gemeinsame Einstellungen
    st.subheader("⚙️ Gemeinsame Einstellungen")
    
    common_col1, common_col2 = st.columns(2)
    
    with common_col1:
        min_premium = st.number_input(
            "Mindest-Prämie für wöchentliche Calls ($)",
            min_value=0.01,
            max_value=1.00,
            value=0.05,
            step=0.01,
            help="Calls mit geringerer Prämie werden nicht verkauft"
        )
    
    with common_col2:
        st.metric("Aktueller Kurs", f"{curr_symbol}{current_price * fx_rate:.2f}")
    
    # Berechnung starten
    if st.button("🔄 Strategien berechnen", type="primary", use_container_width=True):
        
        with st.spinner("Berechne Strategien..."):
            # Strategie A berechnen
            settings_a = {
                'long_call_pct': long_call_pct_a,
                'short_put_pct': short_put_pct_a,
                'hedge_put_pct': hedge_put_pct_a
            }
            result_a = calculate_custom_strategy(
                analyzer, metrics, settings_a, target_risk_a,
                source_currency, target_currency
            )
            
            # Strategie B berechnen
            settings_b = {
                'long_call_pct': long_call_pct_b,
                'short_put_pct': short_put_pct_b,
                'hedge_put_pct': hedge_put_pct_b
            }
            result_b = calculate_custom_strategy(
                analyzer, metrics, settings_b, target_risk_b,
                source_currency, target_currency
            )
        
        # Speichere Ergebnisse in Session State für Backtest
        st.session_state['strategy_result_a'] = result_a
        st.session_state['strategy_result_b'] = result_b
        st.session_state['min_premium'] = min_premium
        
        st.divider()
        
        # Ergebnisse anzeigen
        col_res_a, col_res_b = st.columns(2)
        
        # Strategie A Ergebnisse
        with col_res_a:
            display_strategy_result(result_a, "A", curr_symbol, target_currency, 
                                   metrics, min_premium, analyzer)
        
        # Strategie B Ergebnisse
        with col_res_b:
            display_strategy_result(result_b, "B", curr_symbol, target_currency,
                                   metrics, min_premium, analyzer)
        
        # Vergleichstabelle
        if result_a['success'] and result_b['success']:
            st.divider()
            st.subheader("📊 Direkter Vergleich")
            
            combo_a = result_a['combination']
            combo_b = result_b['combination']
            fx = result_a['fx_rate']
            
            comparison_data = {
                'Metrik': [
                    'Kontrakte',
                    f'Max. Risiko ({target_currency})',
                    'Prämienrendite (p.a.)',
                    'vs. Dividende',
                    'Kurspartizipation',
                    f'Long Call Strike ({target_currency})',
                    f'Short Put Strike ({target_currency})',
                    f'Hedge Put Strike ({target_currency})',
                    f'Netto-Kosten ({target_currency})'
                ],
                '🅰️ Strategie A': [
                    combo_a['num_contracts'],
                    f"{curr_symbol}{combo_a['max_risk_chf']:,.0f}",
                    f"{combo_a['premium_yield']:.1f}%",
                    f"{combo_a['vs_dividend']:+.1f}%",
                    f"{combo_a['upside_participation']*100:.0f}%",
                    f"{curr_symbol}{combo_a['long_call']['strike']*fx:.2f} ({combo_a['long_call']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_a['short_put']['strike']*fx:.2f} ({combo_a['short_put']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_a['hedge_put']['strike']*fx:.2f} ({combo_a['hedge_put']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_a['net_cost']*fx:,.0f}"
                ],
                '🅱️ Strategie B': [
                    combo_b['num_contracts'],
                    f"{curr_symbol}{combo_b['max_risk_chf']:,.0f}",
                    f"{combo_b['premium_yield']:.1f}%",
                    f"{combo_b['vs_dividend']:+.1f}%",
                    f"{combo_b['upside_participation']*100:.0f}%",
                    f"{curr_symbol}{combo_b['long_call']['strike']*fx:.2f} ({combo_b['long_call']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_b['short_put']['strike']*fx:.2f} ({combo_b['short_put']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_b['hedge_put']['strike']*fx:.2f} ({combo_b['hedge_put']['strike_pct']:+.1f}%)",
                    f"{curr_symbol}{combo_b['net_cost']*fx:,.0f}"
                ]
            }
            
            df_comparison = pd.DataFrame(comparison_data)
            st.dataframe(df_comparison, use_container_width=True, hide_index=True)
            
            # Empfehlung
            st.markdown("### 💡 Empfehlung")
            
            if combo_a['premium_yield'] > combo_b['premium_yield']:
                better = "A"
                yield_diff = combo_a['premium_yield'] - combo_b['premium_yield']
            else:
                better = "B"
                yield_diff = combo_b['premium_yield'] - combo_a['premium_yield']
            
            st.success(f"**Strategie {better}** hat eine um **{yield_diff:.1f}%** höhere Prämienrendite.")
    
    # ==================
    # BACKTEST SEKTION
    # ==================
    st.divider()
    st.subheader("📊 Backtest-Vergleich")
    
    st.markdown("""
    Simulation beider Strategien mit historischen Kursdaten.
    - Optionen werden zum **Mittelkurs** (Mid) gekauft/verkauft
    - Kurzfristige Calls werden **wöchentlich gerollt** (wenn Prämie > Minimum)
    - **Beide Strategien** werden parallel simuliert und verglichen
    """)
    
    # Prüfe ob Strategien berechnet wurden
    if 'strategy_result_a' not in st.session_state or 'strategy_result_b' not in st.session_state:
        st.info("👆 Berechne zuerst die Strategien oben, dann kannst du den Backtest starten.")
        return
    
    result_a = st.session_state['strategy_result_a']
    result_b = st.session_state['strategy_result_b']
    min_premium = st.session_state.get('min_premium', 0.05)
    
    if not result_a['success'] and not result_b['success']:
        st.warning("Beide Strategien konnten nicht berechnet werden. Backtest nicht möglich.")
        return
    
    # Backtest-Einstellungen
    bt_col1, bt_col2, bt_col3 = st.columns(3)
    
    with bt_col1:
        default_start = datetime.now() - timedelta(days=90)
        backtest_start = st.date_input(
            "Startdatum",
            value=default_start,
            min_value=datetime.now() - timedelta(days=730),
            max_value=datetime.now() - timedelta(days=7),
            help="Beginn des Backtest-Zeitraums",
            key="bt_start"
        )
    
    with bt_col2:
        backtest_days = st.number_input(
            "Anzahl Tage",
            min_value=7,
            max_value=365,
            value=60,
            step=7,
            help="Dauer des Backtests in Tagen",
            key="bt_days"
        )
    
    with bt_col3:
        st.metric(
            "Min. Call-Prämie",
            f"${min_premium:.2f}",
            help="Calls unter dieser Prämie werden nicht verkauft"
        )
    
    # Backtest starten
    if st.button("🔄 Backtest für beide Strategien starten", type="primary", use_container_width=True):
        start_dt = datetime.combine(backtest_start, datetime.min.time())
        
        with st.spinner(f"Berechne Backtests ({backtest_days} Tage)..."):
            # Backtest A
            if result_a['success']:
                backtest_a = run_simple_backtest(
                    analyzer=analyzer,
                    combination=result_a['combination'],
                    start_date=start_dt,
                    num_days=backtest_days,
                    current_price=current_price,
                    source_currency=source_currency,
                    target_currency=target_currency,
                    min_call_premium=min_premium
                )
            else:
                backtest_a = {'success': False, 'error': 'Strategie A nicht verfügbar'}
            
            # Backtest B
            if result_b['success']:
                backtest_b = run_simple_backtest(
                    analyzer=analyzer,
                    combination=result_b['combination'],
                    start_date=start_dt,
                    num_days=backtest_days,
                    current_price=current_price,
                    source_currency=source_currency,
                    target_currency=target_currency,
                    min_call_premium=min_premium
                )
            else:
                backtest_b = {'success': False, 'error': 'Strategie B nicht verfügbar'}
        
        # Vergleich anzeigen
        display_backtest_comparison(backtest_a, backtest_b, curr_symbol, target_currency)


def display_strategy_result(result: dict, label: str, curr_symbol: str, 
                           target_currency: str, metrics: dict,
                           min_premium: float, analyzer: StockAnalyzer):
    """Zeigt das Ergebnis einer Strategie an."""
    
    st.markdown(f"### Ergebnis Strategie {label}")
    
    if not result['success']:
        st.error("Strategie konnte nicht berechnet werden")
        for w in result.get('warnings', []):
            st.warning(w)
        return
    
    combo = result['combination']
    fx = result['fx_rate']
    
    # Warnungen
    for w in result.get('warnings', []):
        st.warning(w)
    
    # Hauptmetriken
    st.metric("Kontrakte", combo['num_contracts'])
    st.metric(f"Max. Risiko ({target_currency})", f"{curr_symbol}{combo['max_risk_chf']:,.0f}")
    
    div_yield = metrics.get('dividend_yield', 0)
    delta_color = "normal" if combo['premium_yield'] > div_yield else "inverse"
    st.metric(
        "Prämienrendite (p.a.)",
        f"{combo['premium_yield']:.1f}%",
        delta=f"{combo['vs_dividend']:+.1f}% vs. Div.",
        delta_color=delta_color
    )
    
    st.divider()
    
    # Komponenten
    st.markdown("**Komponenten:**")
    
    lc = combo['long_call']
    st.write(f"🔵 **Long Call**: {curr_symbol}{lc['strike']*fx:.2f} "
            f"(Ziel: {lc['target_pct']:+.1f}% → Tatsächlich: {lc['strike_pct']:+.1f}%)")
    st.caption(f"   Verfall: {lc['expiry']} | Prämie: {curr_symbol}{lc['premium']*fx:.2f} | IV: {lc['iv']:.1f}%")
    
    sp = combo['short_put']
    st.write(f"🔴 **Short Put**: {curr_symbol}{sp['strike']*fx:.2f} "
            f"(Ziel: {sp['target_pct']:+.1f}% → Tatsächlich: {sp['strike_pct']:+.1f}%)")
    st.caption(f"   Verfall: {sp['expiry']} | Prämie: {curr_symbol}{sp['premium']*fx:.2f} | IV: {sp['iv']:.1f}%")
    
    hp = combo['hedge_put']
    st.write(f"🟡 **Hedge Put**: {curr_symbol}{hp['strike']*fx:.2f} "
            f"(Ziel: {hp['target_pct']:+.1f}% → Tatsächlich: {hp['strike_pct']:+.1f}%)")
    st.caption(f"   Verfall: {hp['expiry']} | Kosten: {curr_symbol}{hp['premium']*fx:.2f} | IV: {hp['iv']:.1f}%")
    
    st.divider()
    
    # Netto-Position
    net_cost = combo['net_cost']
    if net_cost > 0:
        st.error(f"Netto-Kosten: {curr_symbol}{net_cost * fx:,.2f}")
    else:
        st.success(f"Netto-Einnahme: {curr_symbol}{abs(net_cost) * fx:,.2f}")
    
    # Hebel
    current_price = metrics.get('current_price', 0)
    controlled_value = combo['num_contracts'] * 100 * current_price * fx
    leverage = controlled_value / combo['capital_required_chf'] if combo['capital_required_chf'] > 0 else 0
    st.info(f"Hebel: {leverage:.1f}x | Kontrolliert: {curr_symbol}{controlled_value:,.0f}")
    
    st.divider()
    
    # Kurzfristige Calls
    st.markdown("**🟢 Wöchentliche Calls:**")
    signals = calculate_short_call_signals(analyzer, metrics, combo['num_contracts'], min_premium)
    
    if signals['premium_too_low']:
        st.warning(f"⚠️ {signals['recommendation']}")
    elif signals['num_calls_to_sell'] > 0:
        st.success(f"✅ {signals['recommendation']}: {signals['num_calls_to_sell']} Kontrakte")
        st.caption(f"Strike: {curr_symbol}{signals['strike_recommendation']*fx:.2f} | "
                  f"Erw. Prämie: ${signals['expected_premium']:.2f}")
    else:
        st.info(f"ℹ️ {signals['recommendation']}")


# ============================================================================
#                    DISPLAY OPTIONS ANALYSIS (gekürzte Version)
# ============================================================================


def display_options_analysis(analyzer: StockAnalyzer, metrics: dict,
                            source_currency: str, target_currency: str,
                            curr_symbol: str):
    """Zeigt die Optionsanalyse an (vereinfachte Version für Tab 6)."""
    
    st.markdown("""
    <div class="strategy-box">
    <h4>Aktuelle Optionsketten</h4>
    <p>Übersicht der verfügbaren Optionen für die 4-Komponenten-Strategie.</p>
    </div>
    """, unsafe_allow_html=True)
    
    current_price = metrics.get('current_price', 0)
    fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
    
    # Börsenzeiten-Warnung
    market_open, market_msg = is_market_open()
    if not market_open:
        st.warning(market_msg)
    
    # Optionen laden
    with st.spinner("Lade Optionsketten..."):
        strategy_options = analyzer.get_strategy_options()
    
    # Übersicht der Verfalltermine
    st.subheader("📅 Verfügbare Laufzeiten")
    
    col1, col2, col3, col4 = st.columns(4)
    
    strategies = [
        ('Long Call (6-12 Mo)', 'long_call_buy', col1),
        ('Short Put (12-24 Mo)', 'long_put_sell', col2),
        ('Hedge Put (3-6 Mo)', 'hedge_put_buy', col3),
        ('Short Call (1-2 Wo)', 'short_call_sell', col4),
    ]
    
    for name, key, col in strategies:
        with col:
            strat = strategy_options.get(key, {})
            if strat and strat.get('options') is not None:
                st.success(f"**{name}**")
                st.write(f"Verfall: {strat.get('expiration', 'N/A')}")
                st.write(f"Tage: {strat.get('days', 0)}")
            else:
                st.error(f"**{name}**")
                st.write("Nicht verfügbar")
    
    # Verfügbare Strikes anzeigen
    available_strikes = get_available_strikes(analyzer)
    if available_strikes:
        with st.expander("📋 Verfügbare Strikes"):
            st.write(f"Anzahl: {len(available_strikes)}")
            st.write(f"Bereich: ${min(available_strikes):.2f} - ${max(available_strikes):.2f}")
            
            # Strikes um aktuellen Kurs
            near_strikes = [s for s in available_strikes if abs(s - current_price) / current_price < 0.2]
            st.write(f"Strikes ±20%: {len(near_strikes)}")


def display_dividend_history(analyzer: StockAnalyzer, source_currency: str, 
                            target_currency: str, curr_symbol: str):
    """Zeigt Dividenden-Historie an."""
    try:
        dividends = analyzer.stock.dividends
        if dividends is not None and len(dividends) > 0:
            if dividends.index.tz is not None:
                dividends.index = dividends.index.tz_localize(None)
            
            ten_years_ago = datetime.now() - timedelta(days=3650)
            recent_dividends = dividends[dividends.index >= ten_years_ago]
            
            if len(recent_dividends) > 0:
                st.subheader("📈 Dividenden-Historie (10 Jahre)")
                
                fx_rate = currency_converter.get_exchange_rate(source_currency, target_currency)
                div_df = pd.DataFrame({
                    'Datum': recent_dividends.index,
                    f'Dividende ({target_currency})': recent_dividends.values * fx_rate
                })
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=div_df['Datum'],
                    y=div_df[f'Dividende ({target_currency})'],
                    marker_color='#26a69a'
                ))
                fig.update_layout(
                    title="Dividendenzahlungen",
                    height=300,
                    template='plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)
    except:
        pass


# ============================================================================
#                           HAUPTANWENDUNG
# ============================================================================


def main():
    st.title("📊 Aktienanalyse für Optionenstrategie")
    st.markdown("*Analyse-Tool für sichere Rendite zur Rentenergänzung - Version 3.0 (Variable Strikes + Vergleich)*")
    
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
            index=0,
            help="Alle Beträge werden in diese Währung umgerechnet"
        )
        
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
        
        **NEU in v3.0:**
        - Variable Strike-% Eingabe
        - Negative % für ITM erlaubt
        - Strategie A/B Vergleich
        - Min. Prämie für Calls ($0.05)
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
        
        source_currency = metrics.get('currency', 'USD')
        curr_symbol = 'CHF ' if display_currency == 'CHF' else ('€' if display_currency == 'EUR' else '$')
        
        current_price_converted = currency_converter.convert(
            metrics.get('current_price', 0), 
            source_currency, 
            display_currency
        )
        
        # Header
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
        
        # Tabs - jetzt mit Strategie-Vergleich statt einfachem Builder
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📁 Holdings",
            "📊 Kennzahlen",
            "📈 Chart 5 Jahre",
            "📉 Chart 1 Jahr",
            "🗓️ Saisonalität",
            "⚡ Optionsanalyse",
            "🎯 Strategie-Vergleich"
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
            else:
                st.info(f"{analyzer.ticker} ist eine Einzelaktie - keine Holdings verfügbar")
                
                st.markdown("**Unternehmensinformationen:**")
                company_info = {
                    'Name': metrics.get('name', 'N/A'),
                    'Sektor': metrics.get('sector', 'N/A'),
                    'Industrie': metrics.get('industry', 'N/A'),
                    'Börse': metrics.get('exchange', 'N/A'),
                    'Währung': metrics.get('currency', 'N/A'),
                }
                for key, value in company_info.items():
                    st.write(f"**{key}:** {value}")
        
        # TAB 2: Kennzahlen
        with tab2:
            st.header(f"📊 Wesentliche Kennzahlen (in {display_currency})")
            display_three_thumbs(thumbs)
            
            st.divider()
            
            # Wichtige Termine
            st.subheader("📅 Wichtige Termine")
            dates_info = analyzer.get_upcoming_dates()
            
            term_cols = st.columns(2)
            with term_cols[0]:
                st.info(f"📅 Ex-Dividenden: **{dates_info['ex_dividend_date_str']}**")
            with term_cols[1]:
                st.info(f"📊 Earnings: **{dates_info['earnings_date_str']}**")
            
            st.divider()
            
            # Kennzahlen-Grid
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("💰 Bewertung")
                st.metric("Marktkapitalisierung", format_number(metrics.get('market_cap', 0), 'currency', source_currency, display_currency))
                st.metric("P/E Ratio", f"{metrics.get('pe_ratio', 0):.2f}")
                st.metric("Forward P/E", f"{metrics.get('forward_pe', 0):.2f}")
            
            with col2:
                st.subheader("💵 Cash Flow")
                st.metric("Free Cash Flow", format_number(metrics.get('free_cash_flow', 0), 'currency', source_currency, display_currency))
                st.metric("FCF Yield", f"{metrics.get('fcf_yield', 0):.2f}%")
            
            with col3:
                st.subheader("📈 Dividende")
                st.metric("Dividendenrendite", f"{metrics.get('dividend_yield', 0):.2f}%")
                div_rate_converted = currency_converter.convert(metrics.get('dividend_rate', 0), source_currency, display_currency)
                st.metric(f"Dividende (p.a.)", f"{curr_symbol}{div_rate_converted:.2f}")
            
            st.divider()
            display_dividend_history(analyzer, source_currency, display_currency, curr_symbol)
        
        # TAB 3: Chart 5 Jahre
        with tab3:
            st.header(f"📈 Kursverlauf 5 Jahre")
            
            chart_fx_rate = currency_converter.get_exchange_rate(source_currency, display_currency)
            
            if display_currency != source_currency:
                st.info(f"📊 Historische Währungsumrechnung: {source_currency} → {display_currency}")
            
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
                    st.subheader("📊 Performance-Statistiken")
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
        
        # TAB 7: Strategie-Vergleich (NEU!)
        with tab7:
            display_strategy_builder_with_comparison(analyzer, metrics, source_currency, display_currency, curr_symbol)


if __name__ == "__main__":
    main()
