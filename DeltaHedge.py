import numpy as np
from scipy.stats import norm
import datetime
import pandas as pd

from alpaca.trading.client import TradingClient, GetOptionContractsRequest
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest
from alpaca.data.requests import StockQuotesRequest
from alpaca.trading.enums import AssetStatus, OrderType, QueryOrderStatus, OrderSide, TimeInForce, ContractType, ExerciseStyle
from alpaca.data.historical import StockHistoricalDataClient

# Alpaca API credentials
api_key = ‘YOUR API KEY’
secret_key = ‘YOUR SECRET API KEY’

# Initialize the Alpaca API
trading_client = TradingClient(api_key, secret_key, paper = True)

def get_sp500_stocks():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    response = requests.get(url)
    sp500_table = pd.read_html(response.text, header=0)[0]
    return sp500_table['Symbol'].tolist()

stocks = get_sp500_stocks()
print(f"Total S&P 500 stocks: {len(stocks)}")