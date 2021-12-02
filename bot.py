import datetime
import json
import logging
import os
import time
import sys
import httpx
import tweepy
import tda_api
from pytz import timezone

def main():
    bot = SpaceStocksTwitterBot()
    bot.run()

def tweet_market_open():
    attempts = 0
    bot = SpaceStocksTwitterBot()
    while True:
        try:
            bot.tweet_market_open()
            attempts += 1
            break
        except httpx.HTTPError as e:
            print('Caught httpx.HTTPError: {}: trying again...'.format(e))
            attempts += 1
            time.sleep(1)
            continue
        except json.decoder.JSONDecodeError as e:
            print('Caught json.decoder.JSONDecodeError: {}: trying again...'.format(e))
            attempts += 1
            time.sleep(1)
            continue
    print('tweet_market_open attempts: {}'.format(attempts))

def tweet_market_close():
    attempts = 0
    bot = SpaceStocksTwitterBot()
    while True:
        try:
            bot.tweet_market_wrapup()
            attempts += 1
            break
        except httpx.HTTPError as e:
            print('Caught httpx.HTTPError: {}: trying again...'.format(e))
            attempts += 1
            time.sleep(1)
            continue
        except json.decoder.JSONDecodeError as e:
            print('Caught json.decoder.JSONDecodeError: {}: trying again...'.format(e))
            attempts += 1
            time.sleep(1)
            continue
    print('tweet_market_close attempts: {}'.format(attempts))

class SpaceStocksTwitterBot():

    def __init__(self, api_keys_filename=None):
        self.scriptpath = os.path.abspath(os.path.dirname(__file__))
        if api_keys_filename: credentials = self.load_credentials(api_keys_filename)
        else: credentials = self.load_credentials('api_keys.json')
        self.logger = self.setup_logging()
        self.logger.info('Set scriptpath: {}'.format(self.scriptpath))
        self.twitter_api = self.get_twitter_api(credentials)
        self.tda_client = tda_api.get_client(credentials['tda_api_key'], self.scriptpath)
        self.bot_timeout = 1
        self.market_open_hour = 9
        self.market_open_minute = 45
        self.market_close_hour = 16 # 4PM EST
        self.symbols = [
            ['RKLB', 'ASTR', 'SPCE', 'MNTS', 'NGCA', 'AJRD', 'BA', 'LMT', 'NOC', 'TWNT'],
            ['RDW', 'BKSY', 'MAXR', 'DMYQ', 'GD', 'PKE', 'RTX', 'ATRO', 'KTOS', 'MYNA'],
            ['ASTS', 'CFV', 'SPIR', 'DISH', 'IRDM', 'GSAT', 'OSAT', 'TSAT', 'VSAT']
        ]

    def setup_logging(self):
        filepath = os.path.join(self.scriptpath, 'bot.log')
        logging.basicConfig(filename=filepath, level=logging.INFO,
            format='%(asctime)s:%(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
        return logging.getLogger('main')

    def load_credentials(self, filename):
        filepath = os.path.join(self.scriptpath, filename)
        with open(filepath, 'r') as fp:
            return json.loads(fp.read())

    def auth(self, credentials):
        auth = tweepy.OAuthHandler(
            credentials['consumer_key'], 
            credentials['consumer_secret'])
        auth.set_access_token(credentials['access_token'], credentials['access_secret'])
        return auth

    def get_twitter_api(self, credentials):
        auth = self.auth(credentials)
        return tweepy.API(auth)

    def get_est_time(self):
        tz = timezone('America/New_York')
        return datetime.datetime.now(tz)

    def send_tweet(self, text):
        return self.twitter_api.update_status(text)._json['id']

    def reply_to_tweet(self, tweet_id, text):
        return self.twitter_api.update_status(status=text, in_reply_to_status_id=tweet_id, 
            auto_populate_reply_metadata=True)._json['id']

    def create_open_tweets(self, quotes, dt):
        thread_tweets = []
        current_tweet = '{}/{} MARKET-OPEN UPDATE\n\n'.format(dt.month, dt.day)
        all_symbols = self.get_symbols()
        symbols_obj = [all_symbols[:len(all_symbols)//2], all_symbols[len(all_symbols)//2:]]
        for symbol_list in symbols_obj:
            symbol_list.sort()
            for symbol in symbol_list:
                quote = quotes[symbol]
                line = '${} ${:.2f}\n'.format(symbol, quote['openPrice'])
                current_tweet = current_tweet + line
            thread_tweets.append(current_tweet[:-1])
            current_tweet = ''
        return thread_tweets

    def create_wrapup_tweets(self, quotes, dt):
        thread_tweets = []
        current_tweet = '{}/{} MARKET-CLOSE UPDATE\n\n'.format(dt.month, dt.day)
        for symbol_group in self.symbols:
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

    def send_tweet_thread(self, tweets):
        top_level_tweet = tweets[0]
        replies = tweets[1:]
        tweet_id = self.send_tweet(top_level_tweet)
        top_level_tweet_id = tweet_id
        for reply in replies:
            tweet_id = self.reply_to_tweet(tweet_id, reply)
        return top_level_tweet_id

    def is_market_open(self, dt):
        persistence_file = self.load_persistence_file()
        if 'market_status' not in persistence_file:
            is_market_open = tda_api.is_market_open(self.tda_client, dt)
            persistence_file['market_status'] = {
                'is_market_open': is_market_open,
                'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
            self.save_persistence_file(persistence_file)
            return is_market_open

        market_status_obj = persistence_file['market_status']
        last_market_status_dt = datetime.datetime.strptime(market_status_obj['datetime'], '%d/%m/%Y %H:%M:%S')
        if last_market_status_dt.day == dt.day:
            return market_status_obj['is_market_open']
        else:
            is_market_open = tda_api.is_market_open(self.tda_client, dt)
            persistence_file['market_status'] = {
                'is_market_open': is_market_open,
                'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
            self.save_persistence_file(persistence_file)
            return is_market_open

    def get_symbols(self):
        symbols = []
        for symbol_group in self.symbols: symbols = symbols + symbol_group
        return symbols

    def get_quotes(self):
        symbols = self.get_symbols()
        return self.tda_client.get_quotes(symbols).json()

    def already_tweeted_open(self):
        persistence_file = self.load_persistence_file()
        if 'latest-tweet-updates' not in persistence_file: return False
        latest_tweet_updates = persistence_file['latest-tweet-updates']
        if 'market-open-tweet' not in latest_tweet_updates: return False
        dt_str = latest_tweet_updates['market-open-tweet']['datetime']
        last_open_dt = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
        now = self.get_est_time()
        if now.day == last_open_dt.day: return True
        return False

    def already_tweeted_wrapup(self):
        persistence_file = self.load_persistence_file()
        if 'latest-tweet-updates' not in persistence_file: return False
        latest_tweet_updates = persistence_file['latest-tweet-updates']
        if 'market-wrapup-tweet' not in latest_tweet_updates: return False
        dt_str = latest_tweet_updates['market-wrapup-tweet']['datetime']
        last_wrapup_dt = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
        now = self.get_est_time()
        if now.day == last_wrapup_dt.day: return True
        return False

    def persist_last_open(self, dt):
        persistence_file = self.load_persistence_file()
        if 'latest-tweet-updates' not in persistence_file: persistence_file['latest-tweet-updates'] = {}
        persistence_file['latest-tweet-updates']['market-open-tweet'] = { 'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
        self.save_persistence_file(persistence_file)

    def persist_last_wrapup(self, dt):
        persistence_file = self.load_persistence_file()
        if 'latest-tweet-updates' not in persistence_file: persistence_file['latest-tweet-updates'] = {}
        persistence_file['latest-tweet-updates']['market-wrapup-tweet'] = { 'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
        self.save_persistence_file(persistence_file)

    def save_persistence_file(self, content):
        filepath = os.path.join(self.scriptpath, 'persistence.json')
        with open(filepath, 'w+') as json_file:
            json_file.write(json.dumps(content))

    def load_persistence_file(self):
        filepath = os.path.join(self.scriptpath, 'persistence.json')
        with open(filepath, 'a+') as fp:
            fp.seek(0)
            content = fp.read()
            if content == '': return json.loads('{}')
            else: return json.loads(content)

    def tweet_market_open(self):
        est_time = self.get_est_time()
        mid_day_dt = est_time.replace(hour=12, minute=0)
        market_open = tda_api.is_market_open(self.tda_client, mid_day_dt)
        self.logger.info("tweet_market_open called, market open: '{}'".format(market_open))
        if market_open:
            tweets = self.create_open_tweets(self.get_quotes(), est_time)
            top_level_tweet_id = self.send_tweet_thread(tweets)
            self.logger.info("Sent market-open tweet with id '{}'".format(top_level_tweet_id))

    def tweet_market_wrapup(self):
        est_time = self.get_est_time()
        mid_day_dt = est_time.replace(hour=12, minute=0)
        market_open = tda_api.is_market_open(self.tda_client, mid_day_dt)
        self.logger.info("tweet_market_wrapup called, market open: '{}'".format(market_open))
        if market_open:
            tweets = self.create_wrapup_tweets(self.get_quotes(), est_time)
            top_level_tweet_id = self.send_tweet_thread(tweets)
            self.logger.info("Sent market-close tweet with id '{}'".format(top_level_tweet_id))


    def run(self):
        self.logger.info('SpaceStocksTwitterBot.run() called')
        while True:
            est_time = self.get_est_time()
            mid_day_dt = est_time.replace(hour=12, minute=0)
            if est_time.hour == self.market_open_hour and est_time.minute >= self.market_open_minute:
                if not self.already_tweeted_open() and self.is_market_open(mid_day_dt):
                    tweets = self.create_open_tweets(self.get_quotes(), est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    self.logger.info("Sent market-open tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_open(est_time)
            elif est_time.hour == self.market_close_hour:
                if not self.already_tweeted_wrapup() and self.is_market_open(mid_day_dt):
                    tweets = self.create_wrapup_tweets(self.get_quotes(), est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    self.logger.info("Sent market-close tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_wrapup(est_time)
            time.sleep(self.bot_timeout)

if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) > 0:
        mode = args[0].lower()
        if mode == 'main':
            main()
        elif mode == 'open':
            tweet_market_open()
        elif mode == 'close':
            tweet_market_close()
        else:
            print("'{}' is an unknown argument".format(mode))
    else:
        main()