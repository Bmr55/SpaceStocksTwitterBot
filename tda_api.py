import os
from tda.auth import easy_client

REDIRECT_URI = 'https://localhost:8080/'
TOKEN_FILE = 'tda_token.json'

def get_client(api_key, scriptpath):
    token_path = os.path.join(scriptpath, TOKEN_FILE)
    return easy_client(api_key=api_key, redirect_uri=REDIRECT_URI, token_path=token_path)

def get_quotes(tda_client, symbols):
    return tda_client.get_quotes(symbols).json()

def get_instruments(tda_client, symbols):
    projection = tda_client.Instrument.Projection.FUNDAMENTAL
    instruments = tda_client.search_instruments(symbols, projection)
    return instruments.json()

def get_market_hours(tda_client, dt):
    market = tda_client.Markets('EQUITY')
    response = tda_client.get_hours_for_single_market(market, dt)
    return response.json() # 'json.decoder.JSONDecodeError: Extra data' sometimes arises here

def is_market_open(tda_client, dt):
    response = get_market_hours(tda_client, dt)
    try:
        outer_equity_obj = response['equity']
        if 'EQ' not in outer_equity_obj:
            inner_equity_obj = outer_equity_obj['equity']
        else:
            inner_equity_obj = outer_equity_obj['EQ']
        return inner_equity_obj['isOpen']
    except ValueError as e:
        print(e)
        return False