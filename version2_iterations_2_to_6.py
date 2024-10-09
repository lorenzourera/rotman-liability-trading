import signal
import requests
from time import sleep
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()
API_KEY = os.environ.get("API_KEY")
API_KEY = {'X-API-Key': API_KEY}
shutdown = False

class ApiException(Exception):
    pass

def signal_handler(signum, frame):
    global shutdown
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    shutdown = True

def clear_screen():
    if os.name == "nt":
        os.system('cls')
    else:
        os.system('clear')

def get_tender(session):
    resp = session.get('http://localhost:9999/v1/tenders')
    if resp.ok:
        tender = resp.json()
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
        print(e)

def ticker_bid_ask(session, ticker):
    payload = {'ticker': ticker}
    try:
        resp = session.get('http://localhost:9999/v1/securities/book', params=payload)
        if resp.ok:
            book = resp.json()
            return book
    except Exception as e:
        print(e)

def calculate_wac_and_liquidity(order_books, tender_offer):
    total_cost = 0.0
    total_quantity = 0.0
    tender_offer = tender_offer[0]  # Only do the most recent tender offer if there are multiple
    offer_quantity = tender_offer['quantity']
    offer_price = tender_offer['price']
    action = tender_offer['action']  # 'BUY' or 'SELL'

    # Collect relevant orders from both markets
    relevant_orders = []

    if action == 'BUY':
        relevant_orders.extend(order_books['CRZY_M']['asks'])
        relevant_orders.extend(order_books['CRZY_A']['asks'])
        relevant_orders.extend(order_books['TAME_M']['asks'])
        relevant_orders.extend(order_books['TAME_A']['asks'])
    else:
        relevant_orders.extend(order_books['CRZY_M']['bids'])
        relevant_orders.extend(order_books['CRZY_A']['bids'])
        relevant_orders.extend(order_books['TAME_M']['bids'])
        relevant_orders.extend(order_books['TAME_A']['bids'])

    market_quantities = {'Main Market': 0, 'Alternative Market': 0}

    for order in relevant_orders:
        if total_quantity >= offer_quantity:
            break  # Stop if we've sourced enough liquidity

        available_quantity = order['quantity'] - order['quantity_filled']
        price = order['price']

        if available_quantity > 0:
            quantity_to_take = min(available_quantity, offer_quantity - total_quantity)
            total_cost += quantity_to_take * price
            total_quantity += quantity_to_take
            
            # Determine which market this order came from and log the quantity
            if order['ticker'].endswith('_M'):
                market_quantities['Main Market'] += quantity_to_take
            else:
                market_quantities['Alternative Market'] += quantity_to_take

            # print(f"Order processed: Quantity taken: {quantity_to_take}, Price: {price}, Total Quantity now: {total_quantity}")

    wac = total_cost / total_quantity if total_quantity > 0 else float('inf')

  # Decision based on WAC and tender offer price
# Decision based on WAC and tender offer price
    if total_quantity >= offer_quantity and (action == 'BUY' and wac < offer_price) or (action == 'SELL' and wac > offer_price):
        return "Accept", total_quantity, wac, market_quantities
    elif total_quantity < offer_quantity:
        print(f"Decline reason: Insufficient quantity sourced ({total_quantity} < {offer_quantity})")
        return "Decline", total_quantity, wac, market_quantities
    elif action == 'BUY' and wac > offer_price:
        potential_loss_pct = ((wac - offer_price) / offer_price) * 100
        print(f"Decline reason: Price unfavorable. WAC: {wac:.2f}, Offer Price: {offer_price:.2f}, Potential loss: -{potential_loss_pct:.2f}%")
        return "Decline", total_quantity, wac, market_quantities
    elif action == 'SELL' and wac < offer_price:
        potential_gain_pct = ((offer_price - wac) / offer_price) * 100
        print(f"Decline reason: Price unfavorable. WAC: {wac:.2f}, Offer Price: {offer_price:.2f}, Potential gain lost: -{potential_gain_pct:.2f}%")
        return "Decline", total_quantity, wac, market_quantities



def main():
    with requests.Session() as s:
        s.headers.update(API_KEY)
        
        tick = get_tick(s)
        
        while tick > 5 and tick < 295 and not shutdown:
            clear_screen()
            print(f"Tick: {tick}")

            # Get and filter tender offers. Remove auctions.
            tender_offers = filter_tender_offers(get_tender(s))
            if len(tender_offers) == 0:
                print("No valid tender offers available.")
                sleep(1)
                tick = get_tick(s)
                continue
            
            # Use only the most recent tender offer
            current_tender = tender_offers[0]
            tender_ticker = current_tender['ticker'] 
            
            # Get order books for both stocks separately (for both markets)
            order_books = {
                'CRZY_M': ticker_bid_ask(s, 'CRZY_M'),
                'CRZY_A': ticker_bid_ask(s, 'CRZY_A'),
                'TAME_M': ticker_bid_ask(s, 'TAME_M'),
                'TAME_A': ticker_bid_ask(s, 'TAME_A')
            }

            # Determine which stock's order book to use based on the tender ticker
            relevant_order_book = None
            
            if tender_ticker == 'CRZY_M':
                relevant_order_book = order_books['CRZY_M']
            elif tender_ticker == 'CRZY_A':
                relevant_order_book = order_books['CRZY_A']
            elif tender_ticker == 'TAME_M':
                relevant_order_book = order_books['TAME_M']
            elif tender_ticker == 'TAME_A':
                relevant_order_book = order_books['TAME_A']
            
            if relevant_order_book is None:
                print(f"Unknown stock for ticker: {tender_ticker}")
                sleep(1)
                continue
            
            print("-------------Tender Details----------------")
            pprint(current_tender)
            
            print("----------------Decision------------------")
            decision, total_quantity, wac, market_quantities = calculate_wac_and_liquidity(order_books=order_books, tender_offer=[current_tender])
            
            # Include market information in decision output
            market_type = "Main Market" if tender_ticker.endswith('_M') else "Alternative Market"
            
            if decision == "Accept":
                print(f"Decision: {decision}, Total Quantity Sourced: {total_quantity}, WAC: {wac:.2f}")
                print(f"Market Quantities: {market_quantities}")
                print(f"Market to Reverse Trade: {market_type}")
            else:
                print(f"Decision: {decision}")

            sleep(1)

            tick = get_tick(s)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()