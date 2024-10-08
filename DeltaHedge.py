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

# Set up stock historical data client
stock_historical_data_client = StockHistoricalDataClient(api_key, secret_key)

# Function to get the latest quotes for S&P 500 stocks
def get_latest_quotes(stocks):
    quotes = {}
    for stock in stocks:
        req = StockQuotesRequest(symbol_or_symbols=[stock])
        res = stock_historical_data_client.get_stock_latest_quote(req)
        quotes[stock] = res[stock]
    return quotes

# Get the latest quotes for all S&P 500 stocks
latest_quotes = get_latest_quotes(stocks)
print(f"Total S&P 500 stocks quotes retrieved: {len(latest_quotes)}")

# Function to get options contracts for S&P 500 stocks
def get_options_contracts(stocks):
    options_data = {}
    for stock in stocks:
        options_chain = GetOptionContractsRequest(
            underlying_symbols=[stock],
            status=AssetStatus.ACTIVE,
            expiration_date="2024-07-19",
            type=ContractType.CALL,
            style=ExerciseStyle.AMERICAN,
            limit=5
        )
        options_contracts = trading_client.get_option_contracts(options_chain)
        print(len(options_contracts.option_contracts))
        options_data[stock] = options_contracts.option_contracts
    return options_data

# Get options contracts for all S&P 500 stocks
options_contracts = get_options_contracts(stocks)
print(f"Total options contracts retrieved: {sum(len(v) for v in options_contracts.values())}")

def black_scholes_price(S, K, T, r, sigma, option_type="call"):
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "call":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        raise ValueError("Invalid option type. Must be 'call' or 'put'.")
    
    return price

# Function to calculate theoretical prices for all extracted options contracts
def calculate_theoretical_prices(latest_quotes, options_contracts, r, sigma):
    theoretical_prices = {}
    for stock, contracts in options_contracts.items():
        S = latest_quotes[stock].bid_price
        for contract in contracts:
            K = contract.strike_price
            T = (contract.expiration_date - datetime.datetime.now().date()).days / 365.0
            option_type = "call" if contract.type == ContractType.CALL else "put"
            price = black_scholes_price(S, K, T, r, sigma, option_type)
            theoretical_prices[contract.symbol] = price
    return theoretical_prices

# Set parameters for the Black-Scholes model
risk_free_rate = 0.01 
volatility = 0.2

# Calculate theoretical prices for all options contracts
theoretical_prices = calculate_theoretical_prices(latest_quotes, options_contracts, risk_free_rate, volatility)
print(f"Theoretical prices calculated for {len(theoretical_prices)} options contracts.")

# Set parameters for the Black-Scholes model
# Function to identify and sort mispriced options contracts
def find_mispriced_options(options_contracts, theoretical_prices):
    mispriced_options = []
    for stock, contracts in options_contracts.items():
        for contract in contracts:
            if contract.symbol in theoretical_prices:
                if contract.close_price != None:
                    actual_price = float(contract.close_price)
                    theoretical_price = theoretical_prices[contract.symbol]
                    price_difference = abs(actual_price - theoretical_price)
                    mispriced_options.append({
                        'symbol': contract.symbol,
                        'stock': stock,
                        'actual_price': actual_price,
                        'theoretical_price': theoretical_price,
                        'price_difference': price_difference
                    })
    
    # Sort the options by the price difference in descending order
    mispriced_options.sort(key=lambda x: x['price_difference'], reverse=True)
    
    # Select the top 10 mispriced options
    top_mispriced_options = mispriced_options[:10]
    
    return top_mispriced_options

# Identify the mispriced options
top_mispriced_options = find_mispriced_options(options_contracts, theoretical_prices)
print(f"Top 10 mispriced options: {top_mispriced_options}")

# Function to calculate the delta of an option using the Black-Scholes model
def calculate_delta(S, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    delta = norm.cdf(d1)
    
    return delta

# Function to calculate deltas for all top mispriced options
def calculate_deltas(latest_quotes, top_mispriced_options, r, sigma):
    for option in top_mispriced_options:
        stock = option['stock']
        S = latest_quotes[stock].bid_price
        K = option['theoretical_price']
        expiration_date = next(contract.expiration_date for contract in options_contracts[stock] if contract.underlying_symbol == option['stock'])
        T = (expiration_date - datetime.datetime.now().date()).days / 365.0
        option_type = "call"
        delta = calculate_delta(S, K, T, r, sigma, option_type)
        option['delta'] = delta
    return top_mispriced_options

# Calculate deltas for the top mispriced options
top_mispriced_options_with_deltas = calculate_deltas(latest_quotes, top_mispriced_options, risk_free_rate, volatility)
print(f"Top mispriced options with deltas: {top_mispriced_options_with_deltas}")

# Function to place orders for delta hedging
def place_delta_hedging_orders(trading_client, top_mispriced_options_with_deltas):
    orders = []
    for option in top_mispriced_options_with_deltas:
        stock = option['stock']
        delta = option['delta']
        
        # Place order to buy the call option
        call_order_data = LimitOrderRequest(symbol = option['symbol'],
                                            limit_price = option['actual_price'],
                                            qty = 1,
                                            side = OrderSide.BUY,
                                            time_in_force = TimeInForce.DAY)

        call_order = trading_client.submit_order(order_data = call_order_data)
        orders.append(call_order)
        
        # Place order to short the underlying stock
        short_stock_qty = int(delta * 100)  # Delta * 100 shares per option contract
        stock_order_data = LimitOrderRequest(symbol = stock,
                                             limit_price = latest_quotes[stock].bid_price,
                                             qty = short_stock_qty,
                                             side = OrderSide.SELL,
                                             time_in_force = TimeInForce.DAY)
        stock_order = trading_client.submit_order(order_data = stock_order_data)
        orders.append(stock_order)
    
    return orders

# Place delta hedging orders
orders = place_delta_hedging_orders(trading_client, top_mispriced_options_with_deltas)
print(f"Total orders placed: {len(orders)}")

