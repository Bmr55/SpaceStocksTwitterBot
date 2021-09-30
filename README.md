# Space Stocks Twitter Bot
A twitter bot designed to provide market open, market close, and mover price updates for space sector stocks. 

[Live Twitter Bot](https://twitter.com/SpaceStocksUS)

## Dependencies
* [tweepy](https://pypi.org/project/tweepy/)
* [pytz](https://pypi.org/project/pytz/)
* [tda-api](https://pypi.org/project/tda-api/)


## Run bot in a virtualenv on Linux
```console
virtualenv -v bot-venv
source bot-venv/bin/activate
pip3 install -r requirements.txt
python3 bot.py
```
