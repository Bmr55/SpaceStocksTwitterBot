import tweepy    

def get_twitter_api(credentials):
    auth = authenticate(credentials)
    return tweepy.API(auth)

def authenticate(credentials):
    auth = tweepy.OAuthHandler(
        credentials['consumer_key'], 
        credentials['consumer_secret'])
    auth.set_access_token(credentials['access_token'], credentials['access_secret'])
    return auth

def send_tweet(twitter_api, text):
    return twitter_api.update_status(text)._json['id']

def reply_to_tweet(twitter_api, tweet_id, text):
    return twitter_api.update_status(status=text, in_reply_to_status_id=tweet_id, 
        auto_populate_reply_metadata=True)._json['id']

def send_tweet_thread(twitter_api, tweets):
    top_level_tweet = tweets[0]
    replies = tweets[1:]
    tweet_id = send_tweet(twitter_api, top_level_tweet)
    top_level_tweet_id = tweet_id
    for reply in replies:
        tweet_id = reply_to_tweet(twitter_api, tweet_id, reply)
    return top_level_tweet_id