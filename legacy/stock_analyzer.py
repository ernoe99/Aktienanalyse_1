"""
Aktienanalyse-Tool für Optionenstrategie zur Rentenergänzung
============================================================
Streamlit-basierte Anwendung zur Analyse von Aktien und ETFs
mit Fokus auf sichere Rendite durch Optionsstrategien.

Autor: Claude
Version: 1.0
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
</style>
""", unsafe_allow_html=True)


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
                # Versuche verschiedene Methoden für Holdings
                holdings = None
                
                # Methode 1: Über institutional_holders
                try:
                    holdings = self.stock.institutional_holders
                except:
                    pass
                
                # Methode 2: Über major_holders
                if holdings is None or holdings.empty:
                    try:
                        holdings = self.stock.major_holders
                    except:
                        pass
                
                # Methode 3: Für ETFs - Top Holdings aus Info
                if holdings is None or (hasattr(holdings, 'empty') and holdings.empty):
                    # Erstelle manuelle Holdings-Tabelle aus verfügbaren Daten
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
        metrics['peg_ratio'] = self.info.get('pegRatio', 0)
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
        
        # Dividenden
        metrics['dividend_rate'] = self.info.get('dividendRate', 0)
        metrics['dividend_yield'] = self.info.get('dividendYield', 0) or 0
        metrics['payout_ratio'] = self.info.get('payoutRatio', 0)
        metrics['ex_dividend_date'] = self.info.get('exDividendDate', None)
        metrics['five_year_avg_dividend_yield'] = self.info.get('fiveYearAvgDividendYield', 0)
        
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
    
    def get_dividend_history(self, years: int = 10) -> pd.DataFrame:
        """Holt Dividenden-Historie"""
        try:
            dividends = self.stock.dividends
            if not dividends.empty:
                cutoff_date = datetime.now() - timedelta(days=years*365)
                dividends = dividends[dividends.index >= cutoff_date]
                return dividends
            return pd.Series()
        except Exception as e:
            return pd.Series()
    
    def calculate_avg_dividend_yield_10y(self) -> dict:
        """Berechnet durchschnittliche Dividendenrendite der letzten 10 Jahre"""
        try:
            dividends = self.get_dividend_history(10)
            history = self.get_history("10y")
            
            if dividends.empty or history.empty:
                return {'avg_yield': 0, 'total_dividends': 0, 'dividend_growth': 0}
            
            # Jährliche Dividenden
            dividends_df = dividends.to_frame()
            dividends_df.index = pd.to_datetime(dividends_df.index)
            annual_dividends = dividends_df.resample('Y').sum()
            
            # Durchschnittlicher Jahreskurs
            history.index = pd.to_datetime(history.index)
            annual_prices = history['Close'].resample('Y').mean()
            
            # Berechne jährliche Renditen
            yields = []
            for year in annual_dividends.index:
                if year in annual_prices.index:
                    div = annual_dividends.loc[year].values[0]
                    price = annual_prices.loc[year]
                    if price > 0:
                        yields.append((div / price) * 100)
            
            avg_yield = np.mean(yields) if yields else 0
            total_dividends = dividends.sum()
            
            # Dividendenwachstum (CAGR)
            if len(annual_dividends) >= 2:
                first_div = annual_dividends.iloc[0].values[0]
                last_div = annual_dividends.iloc[-1].values[0]
                years_diff = len(annual_dividends) - 1
                if first_div > 0 and years_diff > 0:
                    dividend_growth = ((last_div / first_div) ** (1/years_diff) - 1) * 100
                else:
                    dividend_growth = 0
            else:
                dividend_growth = 0
            
            return {
                'avg_yield': avg_yield,
                'total_dividends': total_dividends,
                'dividend_growth': dividend_growth,
                'annual_dividends': annual_dividends
            }
        except Exception as e:
            return {'avg_yield': 0, 'total_dividends': 0, 'dividend_growth': 0}
    
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
                    # Ungerades Jahr: nur erste 5 Tage zählen
                    result['thumb3']['value'] = first_5_positive
                    result['thumb3']['description'] = f'Ungerades Jahr: Erste 5 Tage {"positiv" if first_5_positive else "negativ"}'
                else:
                    # Gerades Jahr: 70% erste 5 Tage + 30% gerades Jahr (positiver Bias)
                    # Bei geradem Jahr ist der 30%-Teil immer positiv (historisch positive Tendenz)
                    score = 0.7 * (1 if first_5_positive else 0) + 0.3 * 1  # Gerades Jahr = positiv
                    result['thumb3']['value'] = score >= 0.5
                    result['thumb3']['description'] = f'Gerades Jahr: Score {score:.1%}'
            
            result['details']['is_odd_year'] = is_odd_year
            
            # Gesamtzahl der Daumen
            result['total_thumbs'] = sum([
                result['thumb1']['value'],
                result['thumb2']['value'],
                result['thumb3']['value']
            ])
            
        except Exception as e:
            st.error(f"Fehler bei 3-Daumen-Berechnung: {e}")
        
        return result
    
    def get_options_info(self) -> dict:
        """Holt Optionsinformationen"""
        options_info = {
            'expiration_dates': [],
            'weekly': [],
            'monthly': [],
            'leaps': [],
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
                    elif days_to_exp > 180:
                        options_info['leaps'].append(exp)
                
                # Hole Optionsketten für erste verfügbare Termine
                if expirations:
                    for exp in expirations[:3]:  # Erste 3 Termine
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
        """Berechnet durchschnittliche implizite Volatilität"""
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
                
                # Durchschnittliche IV
                if 'impliedVolatility' in chain['calls'].columns:
                    iv_info['avg_call_iv'] = chain['calls']['impliedVolatility'].mean() * 100
                if 'impliedVolatility' in chain['puts'].columns:
                    iv_info['avg_put_iv'] = chain['puts']['impliedVolatility'].mean() * 100
                
                # ATM IV (nächster Strike zum aktuellen Preis)
                if current_price > 0:
                    calls = chain['calls']
                    atm_calls = calls.iloc[(calls['strike'] - current_price).abs().argsort()[:1]]
                    if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns:
                        iv_info['atm_iv'] = atm_calls['impliedVolatility'].values[0] * 100
                        
        except Exception as e:
            pass
        
        return iv_info
    
    def get_seasonal_data(self) -> pd.DataFrame:
        """Berechnet saisonale Muster auf wöchentlicher Basis"""
        try:
            history = self.get_history("10y")
            if history.empty:
                return pd.DataFrame()
            
            # Wöchentliche Returns
            history = history.copy()
            history['Week'] = history.index.isocalendar().week
            history['Year'] = history.index.year
            history['Return'] = history['Close'].pct_change()
            
            # Wöchentliche Aggregation
            weekly_returns = history.groupby(['Year', 'Week'])['Return'].sum().reset_index()
            
            # Durchschnitt pro Woche
            seasonal = weekly_returns.groupby('Week')['Return'].agg(['mean', 'std', 'count']).reset_index()
            seasonal.columns = ['Week', 'Avg_Return', 'Std_Return', 'Count']
            seasonal['Avg_Return_Pct'] = seasonal['Avg_Return'] * 100
            
            # Positive Wochen Ratio
            positive_weeks = weekly_returns.groupby('Week').apply(
                lambda x: (x['Return'] > 0).sum() / len(x) * 100
            ).reset_index()
            positive_weeks.columns = ['Week', 'Positive_Pct']
            
            seasonal = seasonal.merge(positive_weeks, on='Week')
            
            return seasonal
            
        except Exception as e:
            return pd.DataFrame()


def format_number(value, format_type='number'):
    """Formatiert Zahlen für die Anzeige"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 'N/A'
    
    if format_type == 'currency':
        if abs(value) >= 1e12:
            return f"${value/1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"${value/1e9:.2f}B"
        elif abs(value) >= 1e6:
            return f"${value/1e6:.2f}M"
        else:
            return f"${value:,.2f}"
    elif format_type == 'percent':
        return f"{value*100:.2f}%" if abs(value) < 1 else f"{value:.2f}%"
    elif format_type == 'ratio':
        return f"{value:.2f}"
    else:
        if abs(value) >= 1e9:
            return f"{value/1e9:.2f}B"
        elif abs(value) >= 1e6:
            return f"{value/1e6:.2f}M"
        else:
            return f"{value:,.2f}"


def create_price_chart(df: pd.DataFrame, title: str, show_candles: bool = True) -> go.Figure:
    """Erstellt den Preischart mit allen Indikatoren"""
    
    # Berechne alle Indikatoren
    analyzer_temp = StockAnalyzer.__new__(StockAnalyzer)
    df = analyzer_temp.calculate_moving_averages(df)
    df = analyzer_temp.calculate_bollinger_bands(df)
    df = analyzer_temp.calculate_macd(df)
    df = analyzer_temp.calculate_rsi(df)
    
    # Erstelle Subplots
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(title, 'Volumen', 'MACD', 'RSI')
    )
    
    # Hauptchart (Kerzen oder Linie)
    if show_candles:
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Kurs',
                increasing_line_color='#00c853',
                decreasing_line_color='#ff1744'
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['Close'],
                mode='lines',
                name='Kurs',
                line=dict(color='#2196f3', width=1.5)
            ),
            row=1, col=1
        )
    
    # Bollinger Bänder
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['BB_Upper'],
            mode='lines', name='BB Upper',
            line=dict(color='rgba(128,128,128,0.5)', width=1)
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['BB_Lower'],
            mode='lines', name='BB Lower',
            line=dict(color='rgba(128,128,128,0.5)', width=1),
            fill='tonexty', fillcolor='rgba(128,128,128,0.1)'
        ),
        row=1, col=1
    )
    
    # 200 Tage Durchschnitt
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA_200'],
            mode='lines', name='SMA 200',
            line=dict(color='#ff9800', width=2)
        ),
        row=1, col=1
    )
    
    # 50 Tage Durchschnitt
    fig.add_trace(
        go.Scatter(
            x=df.index, y=df['SMA_50'],
            mode='lines', name='SMA 50',
            line=dict(color='#9c27b0', width=1.5)
        ),
        row=1, col=1
    )
    
    # Volumen
    colors = ['#00c853' if df['Close'].iloc[i] >= df['Open'].iloc[i] 
              else '#ff1744' for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], name='Volumen', marker_color=colors),
        row=2, col=1
    )
    
    # MACD
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD',
                   line=dict(color='#2196f3', width=1.5)),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal',
                   line=dict(color='#ff9800', width=1.5)),
        row=3, col=1
    )
    colors_macd = ['#00c853' if val >= 0 else '#ff1744' for val in df['MACD_Histogram']]
    fig.add_trace(
        go.Bar(x=df.index, y=df['MACD_Histogram'], name='Histogram', marker_color=colors_macd),
        row=3, col=1
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI',
                   line=dict(color='#9c27b0', width=1.5)),
        row=4, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.1)", 
                  line_width=0, row=4, col=1)
    
    # Layout
    fig.update_layout(
        height=900,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        template='plotly_white'
    )
    
    fig.update_yaxes(title_text="Preis", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
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
    
    # Farben basierend auf Rendite
    colors = ['#00c853' if r >= 0 else '#ff1744' for r in seasonal_data['Avg_Return_Pct']]
    
    # Durchschnittliche Rendite
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
    
    # Positive Wochen Anteil
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
    
    # 50% Linie
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


def display_options_analysis(analyzer: StockAnalyzer, metrics: dict):
    """Zeigt die Optionsanalyse an"""
    
    st.subheader("📋 Verfügbare Optionstermine")
    
    options_info = analyzer.get_options_info()
    
    if not options_info['expiration_dates']:
        st.warning("Keine Optionsdaten verfügbar für diesen Ticker.")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📅 Wöchentlich (≤14 Tage)**")
        if options_info['weekly']:
            for exp in options_info['weekly'][:5]:
                st.write(f"• {exp}")
        else:
            st.write("Keine wöchentlichen Optionen")
    
    with col2:
        st.markdown("**📆 Monatlich (15-45 Tage)**")
        if options_info['monthly']:
            for exp in options_info['monthly'][:5]:
                st.write(f"• {exp}")
        else:
            st.write("Keine monatlichen Optionen")
    
    with col3:
        st.markdown("**📊 LEAPS (>180 Tage)**")
        if options_info['leaps']:
            for exp in options_info['leaps'][:5]:
                st.write(f"• {exp}")
            st.write(f"Längster Termin: **{options_info['leaps'][-1]}**")
        else:
            st.write("Keine LEAPS verfügbar")
    
    st.divider()
    
    # Implizite Volatilität
    st.subheader("📈 Volatilitätsanalyse")
    
    iv_info = analyzer.calculate_implied_volatility()
    
    # Historische Volatilität
    history = analyzer.get_history("1y")
    hist_vol = analyzer.calculate_historical_volatility(history) if not history.empty else 0
    
    vol_cols = st.columns(4)
    
    with vol_cols[0]:
        st.metric("ATM Implied Volatility", f"{iv_info['atm_iv']:.1f}%")
    
    with vol_cols[1]:
        st.metric("Historische Volatilität (30d)", f"{hist_vol:.1f}%")
    
    with vol_cols[2]:
        st.metric("Durchschn. Call IV", f"{iv_info['avg_call_iv']:.1f}%")
    
    with vol_cols[3]:
        st.metric("Durchschn. Put IV", f"{iv_info['avg_put_iv']:.1f}%")
    
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
    
    # Strategieempfehlungen
    st.subheader("🎯 Strategieempfehlungen für Optionenstrategie")
    
    current_price = metrics.get('current_price', 0)
    
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
    
    strategy_cols = st.columns(2)
    
    with strategy_cols[0]:
        st.markdown("**🔴 Verkaufte Puts (Langlaufend)**")
        put_strike_conservative = round(current_price * 0.85, 2)
        put_strike_moderate = round(current_price * 0.90, 2)
        put_strike_aggressive = round(bb_lower, 2)
        
        st.write(f"• Konservativ (15% OTM): ${put_strike_conservative:.2f}")
        st.write(f"• Moderat (10% OTM): ${put_strike_moderate:.2f}")
        st.write(f"• BB Lower Band: ${put_strike_aggressive:.2f}")
        
        st.markdown("**🟢 Verkaufte Calls (Kurzlaufend, wöchentlich)**")
        call_strike_30 = round(current_price + atr, 2)
        call_strike_50 = round(current_price + (1.5 * atr), 2)
        call_bb = round(bb_upper, 2)
        
        st.write(f"• 1 ATR über Kurs: ${call_strike_30:.2f}")
        st.write(f"• 1.5 ATR über Kurs: ${call_strike_50:.2f}")
        st.write(f"• BB Upper Band: ${call_bb:.2f}")
    
    with strategy_cols[1]:
        st.markdown("**🔵 Gekaufte Calls (Langlaufend, Sicherung)**")
        st.write(f"• ATM Strike: ${round(current_price, 2)}")
        st.write(f"• Leicht ITM (-5%): ${round(current_price * 0.95, 2)}")
        
        st.markdown("**🟡 Gekaufte Puts (Mittelfristig, Absicherung)**")
        hedge_put = round(current_price * 0.80, 2)
        st.write(f"• 20% OTM: ${hedge_put:.2f}")
        st.write(f"• 15% OTM: ${round(current_price * 0.85, 2)}")
    
    st.divider()
    
    # Margin-Schätzung
    st.subheader("💰 Margin- und Hebel-Schätzung")
    
    # Vereinfachte Margin-Berechnung
    position_value = current_price * 100  # 1 Kontrakt = 100 Aktien
    
    margin_cols = st.columns(3)
    
    with margin_cols[0]:
        put_margin = position_value * 0.20  # Ca. 20% für naked puts
        st.metric("Geschätzte Put-Margin (pro Kontrakt)", 
                  f"${put_margin:,.0f}",
                  help="Ungefähre Margin für einen verkauften Put")
    
    with margin_cols[1]:
        # Bei Hebel 7 benötigtes Kapital
        leverage_7_capital = position_value / 7
        st.metric("Kapital bei Hebel 7 (pro Kontrakt)",
                  f"${leverage_7_capital:,.0f}",
                  help="Benötigtes Eigenkapital bei 7-fachem Hebel")
    
    with margin_cols[2]:
        # Maximale Kontraktanzahl bei verschiedenen Kapitalgrößen
        st.metric("Kontrollierter Wert (1 Kontrakt)",
                  f"${position_value:,.0f}",
                  help="Wert von 100 Aktien")
    
    # Optionsketten anzeigen
    if options_info['chains']:
        st.divider()
        st.subheader("📊 Optionsketten")
        
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
                calls_df['impliedVolatility'] = calls_df['impliedVolatility'] * 100
                calls_df = calls_df.round(2)
                st.dataframe(calls_df, use_container_width=True)
            
            with tab_puts:
                puts_df = chain['puts'][['strike', 'lastPrice', 'bid', 'ask',
                                         'volume', 'openInterest', 'impliedVolatility']].copy()
                puts_df['impliedVolatility'] = puts_df['impliedVolatility'] * 100
                puts_df = puts_df.round(2)
                st.dataframe(puts_df, use_container_width=True)


def generate_summary(analyzer: StockAnalyzer, metrics: dict, thumbs: dict) -> str:
    """Generiert eine Zusammenfassung zum Abspeichern"""
    
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
PEG Ratio:          {metrics.get('peg_ratio', 0):.2f}
Price to Book:      {metrics.get('price_to_book', 0):.2f}
Price to FCF:       {metrics.get('price_to_fcf', 0):.2f}
FCF Yield:          {metrics.get('fcf_yield', 0):.2f}%

--------------------------------------------------------------------------------
                         DIVIDENDE
--------------------------------------------------------------------------------
Dividendenrendite:  {metrics.get('dividend_yield', 0)*100:.2f}%
Dividende (p.a.):   ${metrics.get('dividend_rate', 0):.2f}
Ausschüttungsquote: {metrics.get('payout_ratio', 0)*100:.2f}%
5J Durchschn. Yield:{metrics.get('five_year_avg_dividend_yield', 0):.2f}%

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
                     OPTIONSSTRATEGIE-HINWEISE
--------------------------------------------------------------------------------
Für die Optionenstrategie mit Hebel 7:
- Verkaufte Puts (langlaufend): Strike ca. 10-15% unter aktuellem Kurs
- Verkaufte Calls (wöchentlich): Strike 1-1.5 ATR über aktuellem Kurs
- Gekaufte Calls (langlaufend): ATM oder leicht ITM zur Absicherung
- Gekaufte Puts (mittelfristig): 15-20% OTM zur Absicherung

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
    st.markdown("*Analyse-Tool für sichere Rendite zur Rentenergänzung*")
    
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
        
        st.markdown("**Chart-Einstellungen**")
        chart_type = st.radio("Chart-Typ", ["Kerzen", "Linie"], horizontal=True)
        
        st.divider()
        
        st.markdown("**Über die Strategie**")
        st.info("""
        Diese Analyse unterstützt eine Optionenstrategie mit:
        - 🔴 Verkaufte Puts (langlaufend)
        - 🟢 Verkaufte Calls (wöchentlich, 30-50%)
        - 🔵 Gekaufte Calls (langlaufend, Sicherung)
        - 🟡 Gekaufte Puts (mittelfristig, Absicherung)
        
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
        
        # Header mit Basisinfos
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Ticker", analyzer.ticker)
        with col2:
            st.metric("Aktueller Kurs", f"${metrics.get('current_price', 0):,.2f}")
        with col3:
            change = ((metrics.get('current_price', 0) / metrics.get('previous_close', 1)) - 1) * 100
            st.metric("Tagesänderung", f"{change:+.2f}%")
        with col4:
            st.metric("3-Daumen", f"{thumbs['total_thumbs']}/3 👍")
        
        st.divider()
        
        # Tabs erstellen
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
                    
                    # Alternative Infos anzeigen
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
                
                # Zeige stattdessen Unternehmensinformationen
                st.markdown("**Unternehmensinformationen:**")
                company_info = {
                    'Name': metrics.get('name', 'N/A'),
                    'Sektor': metrics.get('sector', 'N/A'),
                    'Industrie': metrics.get('industry', 'N/A'),
                    'Börse': metrics.get('exchange', 'N/A'),
                    'Währung': metrics.get('currency', 'N/A')
                }
                for key, value in company_info.items():
                    st.write(f"**{key}:** {value}")
                
                # Beschreibung
                description = analyzer.info.get('longBusinessSummary', '')
                if description:
                    with st.expander("📝 Unternehmensbeschreibung"):
                        st.write(description)
        
        # TAB 2: Kennzahlen
        with tab2:
            st.header("📊 Wesentliche Kennzahlen")
            
            # 3-Daumen-Regel
            display_three_thumbs(thumbs)
            
            st.divider()
            
            # Hauptkennzahlen in Spalten
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("💰 Bewertung")
                st.metric("Marktkapitalisierung", format_number(metrics.get('market_cap', 0), 'currency'))
                st.metric("Umsatz (TTM)", format_number(metrics.get('revenue', 0), 'currency'))
                st.metric("P/E Ratio", f"{metrics.get('pe_ratio', 0):.2f}")
                st.metric("Forward P/E", f"{metrics.get('forward_pe', 0):.2f}")
                st.metric("PEG Ratio", f"{metrics.get('peg_ratio', 0):.2f}")
                st.metric("Price to Book", f"{metrics.get('price_to_book', 0):.2f}")
            
            with col2:
                st.subheader("💵 Cash Flow")
                st.metric("Free Cash Flow", format_number(metrics.get('free_cash_flow', 0), 'currency'))
                st.metric("FCF Yield", f"{metrics.get('fcf_yield', 0):.2f}%")
                st.metric("Price to FCF", f"{metrics.get('price_to_fcf', 0):.2f}")
                st.metric("Operating CF", format_number(metrics.get('operating_cash_flow', 0), 'currency'))
                st.metric("EBITDA", format_number(metrics.get('ebitda', 0), 'currency'))
                st.metric("Gewinnmarge", f"{metrics.get('profit_margin', 0)*100:.2f}%")
            
            with col3:
                st.subheader("📈 Dividende")
                st.metric("Dividendenrendite", f"{metrics.get('dividend_yield', 0)*100:.2f}%")
                st.metric("Dividende (p.a.)", f"${metrics.get('dividend_rate', 0):.2f}")
                st.metric("Ausschüttungsquote", f"{metrics.get('payout_ratio', 0)*100:.2f}%")
                st.metric("5J Durchschn. Yield", f"{metrics.get('five_year_avg_dividend_yield', 0):.2f}%")
                
                # 10-Jahres Dividenden-Analyse
                div_analysis = analyzer.calculate_avg_dividend_yield_10y()
                st.metric("10J Durchschn. Yield", f"{div_analysis.get('avg_yield', 0):.2f}%")
                st.metric("Dividendenwachstum (CAGR)", f"{div_analysis.get('dividend_growth', 0):.2f}%")
            
            st.divider()
            
            # Risiko und Volatilität
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
            
            # Earnings-Termine
            st.divider()
            st.subheader("📅 Wichtige Termine")
            
            term_cols = st.columns(2)
            with term_cols[0]:
                ex_div = metrics.get('ex_dividend_date')
                if ex_div:
                    ex_div_date = datetime.fromtimestamp(ex_div).strftime('%d.%m.%Y')
                    st.info(f"📅 Nächster Ex-Dividenden-Tag: **{ex_div_date}**")
                else:
                    st.info("Kein Ex-Dividenden-Datum verfügbar")
            
            with term_cols[1]:
                earnings = metrics.get('earnings_date')
                if earnings:
                    earnings_date = datetime.fromtimestamp(earnings).strftime('%d.%m.%Y')
                    st.warning(f"📊 Nächster Earnings-Termin: **{earnings_date}**")
                else:
                    st.info("Kein Earnings-Datum verfügbar")
        
        # TAB 3: Chart 5 Jahre
        with tab3:
            st.header("📈 Kursverlauf 5 Jahre")
            
            with st.spinner("Lade 5-Jahres-Daten..."):
                history_5y = analyzer.get_history("5y")
                
                if not history_5y.empty:
                    fig_5y = create_price_chart(
                        history_5y, 
                        f"{analyzer.ticker} - 5 Jahre",
                        show_candles=(chart_type == "Kerzen")
                    )
                    st.plotly_chart(fig_5y, use_container_width=True)
                    
                    # Dividenden-Marker hinzufügen
                    dividends = analyzer.get_dividend_history(5)
                    if not dividends.empty:
                        with st.expander("📅 Dividenden-Termine (letzte 5 Jahre)"):
                            div_df = dividends.to_frame()
                            div_df.columns = ['Dividende']
                            div_df.index = pd.to_datetime(div_df.index).strftime('%d.%m.%Y')
                            st.dataframe(div_df, use_container_width=True)
                else:
                    st.error("Keine historischen Daten verfügbar")
        
        # TAB 4: Chart 1 Jahr
        with tab4:
            st.header("📉 Kursverlauf 1 Jahr")
            
            with st.spinner("Lade 1-Jahres-Daten..."):
                history_1y = analyzer.get_history("1y")
                
                if not history_1y.empty:
                    fig_1y = create_price_chart(
                        history_1y,
                        f"{analyzer.ticker} - 1 Jahr",
                        show_candles=(chart_type == "Kerzen")
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
                    
                    # Beste und schlechteste Wochen
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
                    
                    # Aktuelle Woche markieren
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
            st.header("⚡ Optionsanalyse")
            display_options_analysis(analyzer, metrics)
        
        # Zusammenfassung generieren
        st.divider()
        
        if st.button("📄 Zusammenfassung erstellen", type="secondary"):
            summary = generate_summary(analyzer, metrics, thumbs)
            
            st.text_area("Zusammenfassung (kopieren oder speichern)", summary, height=400)
            
            # Download-Button
            st.download_button(
                label="💾 Als Textdatei herunterladen",
                data=summary,
                file_name=f"{analyzer.ticker}_analyse_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )


if __name__ == "__main__":
    main()
