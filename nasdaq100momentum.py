import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from io import StringIO
import streamlit as st
from datetime import datetime
import numpy as np

def get_nasdaq100_stocks():
    url = "https://en.wikipedia.org/wiki/NASDAQ-100"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'id': 'constituents'})
    
    # Wrap the HTML string in StringIO before passing it to read_html
    html_string = str(table)
    html_io = StringIO(html_string)
    
    df = pd.read_html(html_io)[0]
    return df['Ticker'].tolist()

nasdaq100_stocks = get_nasdaq100_stocks()

def fetch_stock_data(ticker):
    stock = yf.Ticker(ticker)
    data = stock.history(period="max", interval="1mo")
    return data

stocks = []
for stock in nasdaq100_stocks:
    try:
        stocks.append(fetch_stock_data(stock))
    except Exception as e:
        print(f"Error fetching data for {stock}: {e}")
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

filtered_data = rollingPctChange.iloc[-1][rollingPctChange.iloc[-1] > 0.02]
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

if nasdaq_data['momentum1yr'].iloc[-1] < 0 and nasdaq_data['momentum6mo'].iloc[-1] < -.05:
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

# Calculate weights based on relative performance
if len(top15) > 0:
    # Find the most recent rebalance date
    today = datetime.today()
    rebalance_dates = [
        datetime(today.year, 1, 1),
        datetime(today.year, 4, 1),
        datetime(today.year, 7, 1),
        datetime(today.year, 10, 1)
    ]
    last_rebalance_date = max([date for date in rebalance_dates if date <= today])
    
    # Find the next rebalance date
    next_rebalance_dates = [
        datetime(today.year, 1, 1),
        datetime(today.year, 4, 1),
        datetime(today.year, 7, 1),
        datetime(today.year, 10, 1),
        datetime(today.year + 1, 1, 1)  # Include the first rebalance date of the next year
    ]
    next_rebalance_date = min([date for date in next_rebalance_dates if date > last_rebalance_date])

    # Get the initial and current prices
    rebalance_date_str = last_rebalance_date.strftime('%Y-%m-%d')
    if rebalance_date_str in data.index:
        rebalance_prices = data.loc[rebalance_date_str, top15.index]
    else:
        # If the rebalance date is not in the index, find the closest previous date
        rebalance_prices = data.loc[data.index[data.index <= rebalance_date_str][-1], top15.index]
    current_prices = data.loc[data.index[-1], top15.index]
    
    # Initial weights are 1/15 for each stock
    initial_investment = 1 / 15
    
    # Calculate the current value of each holding
    current_values = (current_prices / rebalance_prices) * initial_investment
    
    # Calculate the relative weights
    total_value = current_values.sum()
    weights = current_values / total_value

    # Convert weights to percentages
    weights_percentage = weights * 100

    # Add cash to fill the rest of the portfolio if percentages don't add up to 100%
    total_weight_percentage = weights_percentage.sum()
    cash_weight_percentage = 100 - total_weight_percentage

    # Create a DataFrame to display the weights
    holdings_df = pd.DataFrame({'Ticker': top15.index, 'Weight (%)': weights_percentage})
    if cash_weight_percentage > 0:
        cash_df = pd.DataFrame({'Ticker': ['Cash'], 'Weight (%)': [cash_weight_percentage]})
        holdings_df = pd.concat([holdings_df, cash_df], ignore_index=True)

    st.table(holdings_df)

    # Display a bar chart with the calculated weights
    fig, ax = plt.subplots()
    colors = plt.cm.tab20(np.linspace(0, 1, len(holdings_df)))  # Different colors for each bar

    ax.bar(holdings_df['Ticker'], holdings_df['Weight (%)'], color=colors)
    ax.set_xlabel('Ticker')
    ax.set_ylabel('Weight (%)')
    ax.set_title('Portfolio Weights Distribution')
    ax.set_xticklabels(holdings_df['Ticker'], rotation=90)  # Rotate tickers to vertical
    st.pyplot(fig)

    # Calculate the portfolio value at the last rebalance date and the current date
    portfolio_value_rebalance = (rebalance_prices * initial_investment).sum()
    portfolio_value_current = (current_prices * initial_investment).sum()
    total_return = (portfolio_value_current / portfolio_value_rebalance - 1) * 100

    st.write(f"**Last Rebalanced on:** {last_rebalance_date.strftime('%B %d, %Y')}")
    st.write(f"**Next Rebalance on:** {next_rebalance_date.strftime('%B %d, %Y')}")
    st.write(f"**Total Return since last rebalance:** {total_return:.2f}%")
else:
    st.write("No stocks currently held in the portfolio.")
