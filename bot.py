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
        self.bot_timeout = 15
        self.market_open_hour = 9
        self.market_open_minute = 45
        self.market_close_hour = 16 # 4PM EST
        self.market_close_minute = 0
        
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

    def send_tweet_thread(self, tweets):
        top_level_tweet = tweets[0]
        replies = tweets[1:]
        tweet_id = self.send_tweet(top_level_tweet)
        top_level_tweet_id = tweet_id
        for reply in replies:
            tweet_id = self.reply_to_tweet(tweet_id, reply)
        return top_level_tweet_id

    def tweet_movers(self, movers):
        for mover in movers:
            symbol = mover['symbol']
            price = round(mover['regularMarketLastPrice'], 2)
            pct_change = round(mover['regularMarketPercentChangeInDouble'], 2)
            if pct_change > 0:
                tweet = 'PRICE CHANGE ALERT: ${} +${:.2f} ({:.2f}%)'.format(symbol, price, pct_change)
            else:
                tweet = 'PRICE CHANGE ALERT: ${} ${:.2f} ({:.2f}%)'.format(symbol, price, pct_change)
            tweet_id = self.send_tweet(tweet)
            logger.info("Sent mover tweet for symbol '{}' with id '{}'".format(symbol, tweet_id))
            time.sleep(1)

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

    def get_movers(self, quotes):
        movers = []
        symbols = quotes.keys()
        for symbol in symbols:
            quote = quotes[symbol]
            pct_change = quote['regularMarketPercentChangeInDouble']
            if pct_change >= 5.0 or pct_change <= -5.0:
                movers.append(quote)
        return movers

    def filter_movers(self, movers, now):
        filtered_movers = []
        persistence_file = self.load_persistence_file()
        if 'movers' not in persistence_file:
            persistence_file['movers'] = {}
            filtered_movers = movers
        else:
            movers_cooldown = persistence_file['movers']
            for quote in movers:
                symbol = quote['symbol']
                if symbol not in movers_cooldown:
                    filtered_movers.append(quote)
                else:
                    dt_str = movers_cooldown[symbol]['datetime']
                    dt = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M:%S')
                    if dt.day != now.day: filtered_movers.append(quote)
        for filtered_quote in filtered_movers:
            symbol = filtered_quote['symbol']
            movers_cooldown[symbol] = {'datetime': now.strftime('%d/%m/%Y %H:%M:%S')}
        self.save_persistence_file(persistence_file)
        return filtered_movers

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
            json_file.write(json.dumps(content, indent=2))

    def load_persistence_file(self):
        filepath = os.path.join(self.scriptpath, 'persistence.json')
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
                if not self.already_tweeted_open() and self.is_market_open(mid_day_dt):
                    quotes = self.tda_client.get_quotes(SYMBOLS).json()
                    market_open_summary = self.create_market_open_summary(quotes)
                    tweets = self.create_open_tweets(market_open_summary, est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    logger.info("Sent market-open tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_open(est_time)
            elif est_time.hour == self.market_close_hour:
                if not self.already_tweeted_wrapup() and self.is_market_open(mid_day_dt):
                    quotes = self.tda_client.get_quotes(SYMBOLS).json()
                    market_wrapup = self.create_market_wrapup(quotes)
                    tweets = self.create_wrapup_tweets(market_wrapup, est_time)
                    top_level_tweet_id = self.send_tweet_thread(tweets)
                    logger.info("Sent market-close tweet with id '{}'".format(top_level_tweet_id))
                    self.persist_last_wrapup(est_time)

            market_open = est_time.replace(hour=self.market_open_hour, minute=self.market_open_minute)
            market_close = est_time.replace(hour=self.market_close_hour, minute=self.market_close_minute)
            if self.is_market_open(mid_day_dt) and (est_time >= market_open and est_time < market_close):
                resp = self.tda_client.get_quotes(SYMBOLS)
                status_code = resp.status_code
                if status_code != 200:
                    print(status_code)
                quotes = resp.json()
                movers = self.get_movers(quotes)
                filtered_movers = self.filter_movers(movers, est_time)
                self.tweet_movers(filtered_movers)
            time.sleep(self.bot_timeout)

if __name__ == '__main__':
    logger.info('bot.py started')
    bot = SpaceStocksTwitterBot()
    bot.run()