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

## Run bot's main run loop via crontab
```console
@reboot /path/to/dir/venv/bin/python3 /path/to/dir/bot.py main &
```

## Run bot in parts via crontab
```console
CRON_TZ=America/New_York
45 9 * * * TZ=America/New_York /path/to/dir/venv/bin/python3 /path/to/dir/bot.py open
0 16 * * * TZ=America/New_York /path/to/dir/venv/bin/python3 /path/to/dir/bot.py close
```
NOTE: Setting timezones in crontab may not be supported by your OS and instead will require setting the system timezone.