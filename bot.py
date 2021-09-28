import datetime
import json
import logging
import os
import time
import tweepy
import tda_api
from pytz import timezone

SYMBOLS = [
    'RKLB', 'ASTR', 'SPCE', 'MNTS', 'RDW', 'ASTS', 'BKSY',
    'PKE', 'MAXR', 'BA', 'RTX', 'AJRD', 'KTOS', 'NOC',
    'LMT', 'GD', 'OSAT', 'IRDM', 'VSAT', 'GSAT', 'DISH'
]

def setup_logging():
    scriptpath = os.path.abspath(os.path.dirname(__file__))
    filepath = os.path.join(scriptpath, 'bot.log')
    logging.basicConfig(filename=filepath, level=logging.INFO,
        format='%(asctime)s:%(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    return logging.getLogger('main')

logger = setup_logging()

class SpaceStocksTwitterBot():

    def __init__(self, api_keys_filename=None):
        self.scriptpath = os.path.abspath(os.path.dirname(__file__))
        logger.info('Set scriptpath: {}'.format(self.scriptpath))
        if api_keys_filename: credentials = self.load_credentials(api_keys_filename)
        else: credentials = self.load_credentials('api_keys.json')
        self.twitter_api = self.get_twitter_api(credentials)
        self.tda_client = tda_api.get_client(credentials['tda_api_key'], self.scriptpath)
        self.do_nothing_timeout = 1
        self.after_tweet_timeout = (60 * 60) + 1
        self.market_open_hour = 9
        self.market_open_minute = 45
        self.market_close_hour = 16 # 4PM EST
        
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

    def create_market_open_summary(self, quotes):
        summary = []
        symbols = quotes.keys()
        for key in symbols:
            quote = quotes[key]
            summary.append({
                'symbol': key,
                'open': quote['openPrice']
            })
        return summary

    '''
        'regularMarketLastPrice' - close
        'closePrice' - previous close
        change = (regularMarketLastPrice - closePrice) / regularMarketLastPrice
    '''
    def create_market_wrapup(self, quotes):
        wrapup = []
        symbols = quotes.keys()
        for key in symbols:
            quote = quotes[key]
            close = quote['regularMarketLastPrice']
            prev_close = quote['closePrice']
            change = (close - prev_close) / close
            pct_change = round(change * 100, 2)
            wrapup.append({
                'symbol': key,
                'close': close,
                'prev_close': prev_close,
                'change': change,
                'pct_change': pct_change
            })
        return wrapup

    def create_open_tweets(self, summary, dt):
        summary_tweets = []
        current_str = '{}/{} MARKET-OPEN UPDATE\n\n'.format(dt.month, dt.day)
        for symbol_summary in summary:
            line = '${} ${:.2f}\n'.format(symbol_summary['symbol'], symbol_summary['open'])
            if (len(current_str) + len(line)) >= 180:
                summary_tweets.append(current_str[:-1])
                current_str = '' + line
            else:
                current_str = current_str + line
        if len(current_str) > 0: summary_tweets.append(current_str[:-1])
        return summary_tweets

    def create_wrapup_tweets(self, wrapup, dt):
        wrapup_tweets = []
        current_str = '{}/{} MARKET-CLOSE UPDATE\n\n'.format(dt.month, dt.day)
        for summary in wrapup:
            if summary['pct_change'] > 0:
                line = '${} ${:.2f} (+{:.2f}%)\n'.format(summary['symbol'], summary['close'], summary['pct_change'])
            else:
                line = '${} ${:.2f} ({:.2f}%)\n'.format(summary['symbol'], summary['close'], summary['pct_change'])

            if (len(current_str) + len(line)) >= 280:
                wrapup_tweets.append(current_str[:-1])
                current_str = '' + line
            else:
                current_str = current_str + line
        if len(current_str) > 0: wrapup_tweets.append(current_str[:-1])
        return wrapup_tweets

    def send_tweet_thread(self, tweets):
        top_level_tweet = tweets[0]
        replies = tweets[1:]
        tweet_id = self.send_tweet(top_level_tweet)
        top_level_tweet_id = tweet_id
        for reply in replies:
            tweet_id = self.reply_to_tweet(tweet_id, reply)
        return top_level_tweet_id

    def already_tweeted_open(self):
        latest_tweets = self.load_latest_tweets()
        if 'market-open-tweet' not in latest_tweets: return False
        dt_str = latest_tweets['market-open-tweet']['datetime']
        last_open_dt = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
        now = self.get_est_time()
        if now.day == last_open_dt.day: return True
        return False

    def already_tweeted_wrapup(self):
        latest_tweets = self.load_latest_tweets()
        if 'market-wrapup-tweet' not in latest_tweets: return False
        dt_str = latest_tweets['market-wrapup-tweet']['datetime']
        last_wrapup_dt = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
        now = self.get_est_time()
        if now.day == last_wrapup_dt.day: return True
        return False

    def persist_last_open(self, dt):
        latest_tweets = self.load_latest_tweets()
        latest_tweets['market-open-tweet'] = { 'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
        self.save_latest_tweets(latest_tweets)

    def persist_last_wrapup(self, dt):
        latest_tweets = self.load_latest_tweets()
        latest_tweets['market-wrapup-tweet'] = { 'datetime': dt.strftime('%d/%m/%Y %H:%M:%S')}
        self.save_latest_tweets(latest_tweets)

    def save_latest_tweets(self, content):
        filepath = os.path.join(self.scriptpath, 'latest_tweets.json')
        with open(filepath, 'w+') as json_file:
            json_file.write(json.dumps(content))

    def load_latest_tweets(self):
        filepath = os.path.join(self.scriptpath, 'latest_tweets.json')
        with open(filepath, 'a+') as fp:
            fp.seek(0)
            content = fp.read()
            if content == '': return json.loads('{}')
            else: return json.loads(content)

    def test_market_open(self):
        est_time = self.get_est_time()
        quotes = self.tda_client.get_quotes(SYMBOLS).json()
        market_open_summary = self.create_market_open_summary(quotes)
        tweets = self.create_open_tweets(market_open_summary, est_time)
        self.send_tweet_thread(tweets)

    def test_market_wrapup(self):
        est_time = self.get_est_time()
        quotes = self.tda_client.get_quotes(SYMBOLS).json()
        market_wrapup = self.create_market_wrapup(quotes)
        tweets = self.create_wrapup_tweets(market_wrapup, est_time)
        self.send_tweet_thread(tweets)

    def run(self):
        logging.info('SpaceStocksTwitterBot.run() called')
        while True:
            est_time = self.get_est_time()
            mid_day_dt = est_time.replace(hour=12, minute=0)
            if est_time.hour == self.market_open_hour and est_time.minute >= self.market_open_minute:
                if not self.already_tweeted_open() and tda_api.is_market_open(self.tda_client, mid_day_dt):
                    quotes = self.tda_client.get_quotes(SYMBOLS).json()
                    market_open_summary = self.create_market_open_summary(quotes)
                    tweets = self.create_open_tweets(market_open_summary, est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    logger.info("Sent market-open tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_open(est_time)
                    time.sleep(self.after_tweet_timeout)
            elif est_time.hour == self.market_close_hour:
                if not self.already_tweeted_wrapup() and tda_api.is_market_open(self.tda_client, mid_day_dt):
                    quotes = self.tda_client.get_quotes(SYMBOLS).json()
                    market_wrapup = self.create_market_wrapup(quotes)
                    tweets = self.create_wrapup_tweets(market_wrapup, est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    logger.info("Sent market-close tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_wrapup(est_time)
                    time.sleep(self.after_tweet_timeout)
                else:
                    time.sleep(self.do_nothing_timeout)
            else:
                time.sleep(self.do_nothing_timeout)

if __name__ == '__main__':
    logger.info('bot.py started')
    bot = SpaceStocksTwitterBot()
    bot.run()