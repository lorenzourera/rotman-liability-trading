# This is a python example algorithm using REST API for the RIT ALGO1 Case

import signal
import requests
from time import sleep
import os
from dotenv import load_dotenv
from pprint import pprint



load_dotenv()
API_KEY = os.environ.get("API_KEY")
print(f"API KEY {API_KEY}")
API_KEY = {'X-API-Key': API_KEY}
shutdown = False

# this class definition allows us to print error messages and stop the program when needed
class ApiException(Exception):
    pass

# this signal handler allows for a graceful shutdown when CTRL+C is pressed
def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True


# Gets the current/latest tender
def get_tender(session):
    resp = session.get('http://localhost:9999/v1/tenders')
    if resp.ok:
        tender = resp.json()
        print("Tender")
        print(tender)
        return tender
    


# this helper method returns the current 'tick' of the running case
def get_tick(session):
    resp = session.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        # print("Tick Data")
        # print(case)
        return case['tick']
    raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT – User Guide – REST API Documentation.pdf)')

# this helper method returns the bid and ask for a given security
def ticker_bid_ask(session, ticker):
    payload = {'ticker': ticker}
    resp = session.get('http://localhost:9999/v1/securities/book', params=payload)
    if resp.ok:
        book = resp.json()
        pprint("book")
        pprint(book)
        return book['bids'][0]['price'], book['asks'][0]['price']
    raise ApiException('The API key provided in this Python code must match that in the RIT client (please refer to the API hyperlink in the client toolbar and/or the RIT – User Guide – REST API Documentation.pdf)')






def main():
    with requests.Session() as s:
        s.headers.update(API_KEY)
        tick = get_tick(s)
        while tick > 5 and tick < 295 and not shutdown:
            tender = get_tender(s)
            # crzy_m_bid, crzy_m_ask = ticker_bid_ask(s, 'CRZY_M')
            # crzy_a_bid, crzy_a_ask = ticker_bid_ask(s, 'CRZY_A')

            print(tick)
            # if crzy_m_bid > crzy_a_ask:
            #     s.post('http://localhost:9999/v1/orders', params={'ticker': 'CRZY_A', 'type': 'MARKET', 'quantity': 1000, 'action': 'BUY'})
            #     s.post('http://localhost:9999/v1/orders', params={'ticker': 'CRZY_M', 'type': 'MARKET', 'quantity': 1000, 'action': 'SELL'})
            #     sleep(1)

            # if crzy_a_bid > crzy_m_ask:
            #     s.post('http://localhost:9999/v1/orders', params={'ticker': 'CRZY_M', 'type': 'MARKET', 'quantity': 1000, 'action': 'BUY'})
            #     s.post('http://localhost:9999/v1/orders', params={'ticker': 'CRZY_A', 'type': 'MARKET', 'quantity': 1000, 'action': 'SELL'})
            #     sleep(1)
            
            sleep(1)

            # IMPORTANT to update the tick at the end of the loop to check that the algorithm should still run or not
            tick = get_tick(s)

if __name__ == '__main__':
    ## For testing live
    # register the custom signal handler for graceful shutdowns
    # signal.signal(signal.SIGINT, signal_handler)
    # main()


    ## For testing single snapshot
    with requests.Session() as s:
        s.headers.update(API_KEY)
        tick = get_tick(s)
        if tick > 5 and tick < 295 and not shutdown:
            print(f"CRZY OB")
            crzy_m_bid, crzy_m_ask = ticker_bid_ask(s, 'CRZY_M')
            
            



