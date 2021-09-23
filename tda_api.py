import atexit
from tda.auth import easy_client

REDIRECT_URI = 'https://localhost:8080/'
TOKEN_PATH = 'tda_token.json'
API_KEY = ""

def make_webdriver():
    # Import selenium here because it's slow to import
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager

    driver = webdriver.Chrome(ChromeDriverManager().install())
    atexit.register(lambda: driver.quit())
    return driver

def get_client(api_key):
    return easy_client(api_key, REDIRECT_URI, TOKEN_PATH, make_webdriver)

def get_market_hours(client, dt):
    market = client.Markets('EQUITY')
    return client.get_hours_for_single_market(market, dt).json()

def is_market_open(client, dt):
    try:
        return get_market_hours(client, dt)['equity']['EQ']['isOpen']
    except Exception as e:
        print(e)
        return False