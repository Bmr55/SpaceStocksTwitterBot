import datetime
import json
import logging
import os
from pytz import timezone

ONE_MILLION = 1000000
ONE_BILLION = 1000000000

def setup_logging(scriptpath, logfile):
    filepath = os.path.join(scriptpath, logfile)
    logging.basicConfig(filename=filepath, level=logging.INFO,
        format='%(asctime)s:%(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    return logging.getLogger('main')

def load_credentials(scriptpath, filename):
    filepath = os.path.join(scriptpath, filename)
    with open(filepath, 'r') as fp:
        return json.loads(fp.read())

def get_eastern_dt():
    tz = timezone('America/New_York')
    return datetime.datetime.now(tz)

def get_symbols_as_list(symbols):
    symbol_list = list()
    for symbol_group in symbols: symbol_list = symbol_list + symbol_group
    return symbol_list

def get_marketcaps(instruments, quotes):
    result = dict()
    for symbol in instruments.keys():
        quote = quotes[symbol]
        fundamentals = instruments[symbol]['fundamental']
        if fundamentals['marketCap'] == 0.0:
            result[symbol] = fundamentals['sharesOutstanding'] * quote['regularMarketLastPrice']
        else:
            result[symbol] = fundamentals['marketCap'] * 1000000
    return sorted(result.items(), key=lambda x: x[1], reverse=True)

def convert_marketcaps_to_str(marketcaps):
    result = dict()
    for item in marketcaps:
        symbol = item[0]
        cap = item[1]
        if cap < ONE_BILLION:
            result[symbol] = '{}M'.format(round(cap / ONE_MILLION, 2))
        else:
            result[symbol] = '{}B'.format(round(cap / ONE_BILLION, 2))
    return result

def create_open_tweets(symbols, quotes, dt):
    thread_tweets = list()
    current_tweet = '{}/{} MARKET-OPEN UPDATE\n\n'.format(dt.month, dt.day)
    all_symbols = get_symbols_as_list(symbols)
    symbols_obj = [all_symbols[:len(all_symbols)//2], all_symbols[len(all_symbols)//2:]]
    for symbol_list in symbols_obj:
        symbol_list.sort()
        for symbol in symbol_list:
            quote = quotes[symbol]
            if quote['openPrice'] == 0.0:
                continue
            line = '${} ${:.2f}\n'.format(symbol, quote['openPrice'])
            current_tweet = current_tweet + line
        thread_tweets.append(current_tweet[:-1])
        current_tweet = ''
    return thread_tweets

def create_close_tweets(symbols, quotes, dt):
    thread_tweets = list()
    current_tweet = '{}/{} MARKET-CLOSE UPDATE\n\n'.format(dt.month, dt.day)
    for symbol_group in symbols:
        symbol_group.sort()
        for symbol in symbol_group:
            quote = quotes[symbol]
            close = quote['regularMarketLastPrice']
            prev_close = quote['closePrice']
            change = (close - prev_close) / close
            pct_change = round(change * 100, 2)
            if pct_change > 0:
                line = '${} ${:.2f} (+{:.2f}%)\n'.format(symbol, close, pct_change)
            else:
                line = '${} ${:.2f} ({:.2f}%)\n'.format(symbol, close, pct_change)
            current_tweet = current_tweet + line
        thread_tweets.append(current_tweet[:-1])
        current_tweet = ''
    return thread_tweets

def create_marketcap_tweets(marketcap_strs, dt):
    thread_tweets = list()
    current_tweet = '{}/{} MARKET CAP UPDATE\n\n'.format(dt.month, dt.day)
    all_symbols = list(marketcap_strs.keys())
    symbols_obj = [all_symbols[:len(all_symbols)//2], all_symbols[len(all_symbols)//2:]]
    for symbol_list in symbols_obj:
        for symbol in symbol_list:
            cap_str = marketcap_strs[symbol]
            line = '${} ${}\n'.format(symbol, cap_str)
            current_tweet = current_tweet + line
        thread_tweets.append(current_tweet[:-1])
        current_tweet = ''
    return thread_tweets