import os
from tda.auth import easy_client

REDIRECT_URI = 'https://localhost:8080/'
TOKEN_FILE = 'tda_token.json'

def get_client(api_key, scriptpath):
    token_path = os.path.join(scriptpath, TOKEN_FILE)
    return easy_client(api_key=api_key, redirect_uri=REDIRECT_URI, token_path=token_path)

def get_market_hours(client, dt):
    market = client.Markets('EQUITY')
    return client.get_hours_for_single_market(market, dt).json()

def is_market_open(client, dt):
    try:
        response = get_market_hours(client, dt)
        outer_equity_obj = response['equity']
        if 'EQ' not in outer_equity_obj:
            inner_equity_obj = outer_equity_obj['equity']
        else:
            inner_equity_obj = outer_equity_obj['EQ']
        return inner_equity_obj['isOpen']
    except Exception as e:
        return False