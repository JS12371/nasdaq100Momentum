import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from io import StringIO
import streamlit as st
from datetime import datetime

def get_nasdaq100_stocks():
    url = "https://en.wikipedia.org/wiki/NASDAQ-100"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'id': 'constituents'})
    
    html_string = str(table)
    html_io = StringIO(html_string)
    
    df = pd.read_html(html_io)[0]
    return df['Ticker'].tolist()

nasdaq100_stocks = get_nasdaq100_stocks()

def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    data = stock.history(period="max", interval="1mo")
    return data[['Close']]

def get_lookback_period():
    i = 0

    ##need i to be 1 if the month is january, april, july, or october
    ##need i to be 2 if the month is february, may, august, or november
    ##need i to be 3 if the month is march, june, september, or december

    if datetime.now().month in [1, 4, 7, 10]:
        i = 1
    elif datetime.now().month in [2, 5, 8, 11]:
        i = 2
    else:
        i = 3
    return i

stocks = []
for stock in nasdaq100_stocks:
    try:
        stocks.append(fetch_stock_data(stock))
    except:
        pass

# Import NASDAQ index price data
nasdaq = yf.Ticker('^NDX')

data = pd.concat(stocks, keys=nasdaq100_stocks, names=['Ticker', 'Date'])
data = data['Close'].unstack(level=0)
data['NASDAQ'] = nasdaq.history(period="max", interval="1mo")['Close']
data['Date'] = data.index
data['Date'] = pd.to_datetime(data['Date'])
data = data.fillna(-1)

data = data.set_index('Date')
rollingPctChange = data.pct_change(9)
rollingPctChange = rollingPctChange.fillna(-1)

filtered_data = rollingPctChange.iloc[-get_lookback_period()][rollingPctChange.iloc[-get_lookback_period()] > 0.02]
top15 = filtered_data.nlargest(15)

# Find the NASDAQ price data
nasdaq = yf.Ticker('^NDX')

# Find the 1-year momentum
nasdaq_data = nasdaq.history(period="1y", interval="1mo")
nasdaq_data['Date'] = nasdaq_data.index
nasdaq_data['Date'] = pd.to_datetime(nasdaq_data['Date'])
nasdaq_data = nasdaq_data.set_index('Date')
nasdaq_data['momentum1yr'] = nasdaq_data['Close'].pct_change(12)

# Find the 6-month momentum
nasdaq_data['momentum6mo'] = nasdaq_data['Close'].pct_change(6)

if nasdaq_data['momentum1yr'].iloc[-get_lookback_period()] < 0 and nasdaq_data['momentum6mo'].iloc[-get_lookback_period()] < -.05:
    st.write("## Sell all stocks")
    top15 = []

st.title("Momentum-Based Nasdaq Rotational Strategy")
st.markdown("### Backtest Statistics from Jan 1, 2000 to Present")

# Using columns for better layout
col1, col2, col3 = st.columns(3)

col1.metric("Annualized Return", "22.6%")
col1.metric("Max Drawdown", "42.8%")

col2.metric("Annual Standard Deviation", "19.4%")
col2.metric("Alpha", ".117")

col3.metric("Beta", ".763")

st.write("### Current Portfolio Holdings")

# Display the current holdings in a table
if len(top15) > 0:
    today = datetime.today()
    rebalance_dates = [
        datetime(today.year, 1, 1),
        datetime(today.year, 4, 1),
        datetime(today.year, 7, 1),
        datetime(today.year, 10, 1)
    ]
    last_rebalance_date = max([date for date in rebalance_dates if date <= today])
    
    percent_returns = []
    for ticker in top15.index:
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(start=last_rebalance_date, end=today)
            rebalance_price = history['Close'].iloc[0]
            current_price = history['Close'].iloc[-1]
            percent_return = ((current_price - rebalance_price) / rebalance_price) * 100
            percent_returns.append(percent_return)
        except:
            percent_returns.append(None)

    holdings_df = pd.DataFrame({'Ticker': top15.index, 'Percent Return': percent_returns})

    original_weights = [1/len(top15)] * len(top15)
    updated_weights = [(w * (1 + pr/100)) for w, pr in zip(original_weights, percent_returns)]
    normalized_weights = [w / sum(updated_weights) for w in updated_weights]

    holdings_df['Updated Weight'] = normalized_weights

    total_return = sum([pr for pr in percent_returns if pr is not None])
    st.table(holdings_df)

    # Display a pie chart with updated weights for each holding
    fig, ax = plt.subplots()
    ax.pie(normalized_weights, labels=top15.index, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    st.pyplot(fig)
    
    st.write(f"**Last Rebalanced on:** {last_rebalance_date.strftime('%B %d, %Y')}")
    st.write(f"**Total Return Over Current Period:** {total_return:.2f}%")
    st.write(f"lookback {get_lookback_period() - 1} months")
else:
    st.write("No stocks currently held in the portfolio.")
