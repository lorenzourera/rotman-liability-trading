import signal
import requests
from time import sleep
import os
from dotenv import load_dotenv
import logging

load_dotenv()
API_KEY = os.environ.get("API_KEY")
API_KEY = {'X-API-Key': API_KEY}
shutdown = False

# Set up logging configuration
logging.basicConfig(filename='trading_log.txt', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ApiException(Exception):
    pass

def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

def get_tender(session):
    resp = session.get('http://localhost:9999/v1/tenders')
    if resp.ok:
        tender = resp.json()
        logging.info("Tender retrieved")
        logging.info(tender)
        return tender

def filter_tender_offers(tender_offers):
    filtered_offers = [
        offer for offer in tender_offers 
        if 'An institution would like to' in offer.get('caption', '')
    ]
    return filtered_offers   

def get_tick(session):
    resp = session.get('http://localhost:9999/v1/case')
    try:
        if resp.ok:
            case = resp.json()
            return case['tick']
    except Exception as e:
        logging.error(f"Error retrieving tick: {e}")

def ticker_bid_ask(session, ticker):
    payload = {'ticker': ticker}
    try:
        resp = session.get('http://localhost:9999/v1/securities/book', params=payload)
        if resp.ok:
            book = resp.json()
            return book
    except Exception as e:
        logging.error(f"Error retrieving order book for {ticker}: {e}")

def calculate_wac_and_liquidity(order_book, tender_offer):
    total_cost = 0.0
    total_quantity = 0.0
    tender_offer = tender_offer[0]  # Only do the most recent tender offer if there are multiple
    offer_quantity = tender_offer['quantity']
    offer_price = tender_offer['price']
    action = tender_offer['action']  # 'BUY' or 'SELL'

    # Determine relevant orders based on action
    relevant_orders = order_book['asks'] if action == 'BUY' else order_book['bids']

    for order in relevant_orders:
        if total_quantity >= offer_quantity:
            break  # Stop if we've sourced enough liquidity

        available_quantity = order['quantity'] - order['quantity_filled']
        price = order['price']

        if available_quantity > 0:
            quantity_to_take = min(available_quantity, offer_quantity - total_quantity)
            total_cost += quantity_to_take * price
            total_quantity += quantity_to_take

    wac = total_cost / total_quantity if total_quantity > 0 else float('inf')

    if total_quantity >= offer_quantity and (action == 'BUY' and wac < offer_price) or (action == 'SELL' and wac > offer_price):
        return "Accept", total_quantity, wac
    else:
        return "Decline", total_quantity, wac

def main():
    with requests.Session() as s:
        s.headers.update(API_KEY)
        tick = get_tick(s)
        
        while tick > 5 and tick < 295 and not shutdown:
            logging.info(f"Tick: {tick}")

            # Get and filter tender offers. Remove auctions.
            tender_offers = filter_tender_offers(get_tender(s))
            if len(tender_offers) == 0:
                logging.info("No valid tender offers available.")
                sleep(1)
                tick = get_tick(s)
                continue
            
            # Use only the most recent tender offer
            current_tender = tender_offers[0]
            tender_ticker = current_tender['ticker'] 
            
            # Get order books for both stocks separately (for both markets)
            crzy_book = ticker_bid_ask(s, 'CRZY')
            tame_book = ticker_bid_ask(s, 'TAME')

            # Determine which stock's order book to use based on the tender ticker
            if tender_ticker.startswith('CRZY'):
                relevant_order_book = crzy_book
            elif tender_ticker.startswith('TAME'):
                relevant_order_book = tame_book
            else:
                logging.warning(f"Unknown stock for ticker: {tender_ticker}")
                sleep(1)
                continue

            logging.info("-------------Tender Details----------------")
            logging.info(f'Tender Details: {current_tender}')
            
            logging.info("----------------Decision------------------")
            decision = calculate_wac_and_liquidity(order_book=relevant_order_book, tender_offer=[current_tender])
            
            # Include market information in decision output
            market_type = "Main Market" if tender_ticker.endswith('_M') else "Alternative Market"
            if decision[0] == "Accept":
                logging.info(f"Decision: {decision}, Market to Reverse Trade: {market_type}")
            else:
                logging.info(f"Decision: {decision}")

            sleep(1)

            tick = get_tick(s)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()