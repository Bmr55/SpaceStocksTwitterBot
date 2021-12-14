import json
import os
import time
import sys
import httpx
import bot_utils
import tda_api
import tweepy_utils

SYMBOLS = [
    ['RKLB', 'ASTR', 'SPCE', 'MNTS', 'NGCA', 'AJRD', 'BA', 'LMT', 'NOC', 'TWNT'],
    ['RDW', 'BKSY', 'MAXR', 'PL', 'GD', 'PKE', 'RTX', 'ATRO', 'KTOS', 'MYNA'],
    ['ASTS', 'CFV', 'SPIR', 'DISH', 'IRDM', 'GSAT', 'OSAT', 'TSAT', 'VSAT']]
SCRIPTPATH = os.path.abspath(os.path.dirname(__file__))
LOGFILE = 'bot.log'
LOGGER = bot_utils.setup_logging(SCRIPTPATH, LOGFILE)
CREDENTIALS = bot_utils.load_credentials(SCRIPTPATH, filename='api_keys.json')

def tweet_market_open():
    eastern_dt = bot_utils.get_eastern_dt()
    mid_day_dt = eastern_dt.replace(hour=12, minute=0)
    twitter_api = tweepy_utils.get_twitter_api(CREDENTIALS)
    tda_client = tda_api.get_client(CREDENTIALS['tda_api_key'], SCRIPTPATH)
    market_open = tda_api.is_market_open(tda_client, mid_day_dt)
    LOGGER.info("tweet_market_open called, market open: '{}'".format(market_open))
    if market_open:
        tweets = bot_utils.create_open_tweets(SYMBOLS, tda_api.get_quotes(tda_client, bot_utils.get_symbols_as_list(SYMBOLS)), eastern_dt)
        top_level_tweet_id = tweepy_utils.send_tweet_thread(twitter_api, tweets)
        LOGGER.info("Sent market-open tweet with id '{}'".format(top_level_tweet_id))

def tweet_market_close():
    eastern_dt = bot_utils.get_eastern_dt()
    mid_day_dt = eastern_dt.replace(hour=12, minute=0)
    twitter_api = tweepy_utils.get_twitter_api(CREDENTIALS)
    tda_client = tda_api.get_client(CREDENTIALS['tda_api_key'], SCRIPTPATH)
    market_open = tda_api.is_market_open(tda_client, mid_day_dt)
    LOGGER.info("tweet_market_close called, market open: '{}'".format(market_open))
    if market_open:
        tweets = bot_utils.create_close_tweets(SYMBOLS, tda_api.get_quotes(tda_client, bot_utils.get_symbols_as_list(SYMBOLS)), eastern_dt)
        top_level_tweet_id = tweepy_utils.send_tweet_thread(twitter_api, tweets)
        LOGGER.info("Sent market-close tweet with id '{}'".format(top_level_tweet_id))

def tweet_marketcaps():
    eastern_dt = bot_utils.get_eastern_dt()
    twitter_api = tweepy_utils.get_twitter_api(CREDENTIALS)
    tda_client = tda_api.get_client(CREDENTIALS['tda_api_key'], SCRIPTPATH)
    symbols = bot_utils.get_symbols_as_list(SYMBOLS)
    quotes = tda_api.get_quotes(tda_client, SYMBOLS)
    instruments = tda_api.get_instruments(tda_client, symbols)
    marketcaps = bot_utils.get_marketcaps(instruments, quotes)
    marketcap_strs = bot_utils.convert_marketcaps_to_str(marketcaps)
    tweets = bot_utils.create_marketcap_tweets(marketcap_strs, eastern_dt)
    top_level_tweet_id = tweepy_utils.send_tweet_thread(twitter_api, tweets)
    LOGGER.info("tweet_marketcaps called")
    LOGGER.info("Sent marketcap tweet with id '{}'".format(top_level_tweet_id))

if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) > 0:
        attempts = 1
        mode = args[0].lower()
        while True:
            try:
                if mode == 'open':
                    tweet_market_open()
                    print('tweet_market_open attempts: {}'.format(attempts))
                elif mode == 'close':
                    tweet_market_close()
                    print('tweet_market_close attempts: {}'.format(attempts))
                elif mode == 'marketcaps':
                    tweet_marketcaps()
                    print('tweet_marketcaps attempts: {}'.format(attempts))
                else:
                    print("'{}' is an unknown argument".format(mode))
                break
            except httpx.HTTPError as e:
                print('Caught httpx.HTTPError: {}: trying again...'.format(e))
                attempts += 1
                time.sleep(1)
            except json.decoder.JSONDecodeError as e:
                print('Caught json.decoder.JSONDecodeError: {}: trying again...'.format(e))
                attempts += 1
                time.sleep(1)
    else:
        print('Missing argument')