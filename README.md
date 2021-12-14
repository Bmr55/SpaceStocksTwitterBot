# Space Stocks Twitter Bot v1.0
A twitter bot designed to provide market open, market close, and market cap updates for space sector stocks. 

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

## Run bot in parts via crontab
```console
CRON_TZ=America/New_York
30 9 * * 1-5 TZ=America/New_York /path/to/dir/venv/bin/python3 /path/to/dir/bot.py open
0 16 * * 1-5 TZ=America/New_York /path/to/dir/venv/bin/python3 /path/to/dir/bot.py close
0 20 * * 5 TZ=America/New_York /path/to/dir/venv/bin/python3 /path/to/dir/bot.py marketcaps
```
NOTE: Setting timezones in crontab may not be supported by your OS and instead will require setting the system timezone.