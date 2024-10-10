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

def extract_base_ticker(ticker):
    if '_' in ticker:
        return ticker.split('_')[0]  
    return ticker  



def calculate_wac_and_liquidity(order_books, tender_offer, liquidity_buffer=0.1):
    total_cost = 0.0
    total_quantity = 0.0
    tender_offer = tender_offer[0]  # Only do the most recent tender offer if there are multiple
    tender_offer_market_type_bool = '_' in tender_offer['ticker']
    tender_ticker = tender_offer["ticker"]
    base_ticker = extract_base_ticker(tender_ticker)
    offer_quantity = tender_offer['quantity']
    offer_price = tender_offer['price']
    action = tender_offer['action']  # 'BUY' or 'SELL'


    adjusted_offer_quantity = offer_quantity * (1 + liquidity_buffer)

    relevant_orders = []

    # If multiple markets per stock
    if tender_offer_market_type_bool:
        if action == 'SELL': # sell to client, buy from market 
            relevant_orders.extend(order_books['CRZY_M']['asks'])
            relevant_orders.extend(order_books['CRZY_A']['asks'])
            relevant_orders.extend(order_books['TAME_M']['asks'])
            relevant_orders.extend(order_books['TAME_A']['asks'])
            
        else:
            relevant_orders.extend(order_books['CRZY_M']['bids'])
            relevant_orders.extend(order_books['CRZY_A']['bids'])
            relevant_orders.extend(order_books['TAME_M']['bids'])
            relevant_orders.extend(order_books['TAME_A']['bids'])
    else: #single market
        if action == 'SELL':
            relevant_orders.extend(order_books['CRZY']['asks'])
            relevant_orders.extend(order_books['TAME']['asks'])
            try:
                relevant_orders.extend(order_books['BBSN']['asks'])
            except:
                pass
                

        else:
            relevant_orders.extend(order_books['CRZY']['bids'])
            relevant_orders.extend(order_books['TAME']['bids'])
            try:
                relevant_orders.extend(order_books['BBSN']['bids'])
            except:
                pass    


    wac_data = {
        'CRZY': {'WAC': 0.0, 'Quantity': 0, 'MarketQuantities': {'Main Market': 0, 'Alternative Market': 0, 'Normal': 0}},
        'TAME': {'WAC': 0.0, 'Quantity': 0, 'MarketQuantities': {'Main Market': 0, 'Alternative Market': 0, 'Normal': 0}},
        'BBSN': {'WAC': 0.0, 'Quantity': 0, 'MarketQuantities': {'Main Market': 0, 'Alternative Market': 0, 'Normal': 0}}
    }

    contributing_orders = []



    # Filter relevant orders, drop orders that pertain to a different stock
    relevant_orders = [item for item in relevant_orders if base_ticker in item['ticker']]
    # Make sure relevant orders are still sorted properly
    if action == "SELL": # sort asks lowest to highest
        relevant_orders = sorted(relevant_orders, key=lambda x: x['price'])
    else: # sort bids highest to lowest
        relevant_orders = sorted(relevant_orders, key=lambda x: x['price'], reverse=True)


    # print("relevant_orders")
    # print(relevant_orders)

    for order in relevant_orders: # this loop will aggregate liquidity and compute wac recursively until the required volume is reached per market
        
        if total_quantity >= offer_quantity:
            break  # Stop if we've sourced enough liquidity

        available_quantity = order['quantity'] - order['quantity_filled']
        price = order['price']

        if available_quantity > 0:
            quantity_to_take = min(available_quantity, offer_quantity - total_quantity)
            total_cost += quantity_to_take * price
            total_quantity += quantity_to_take

            contributing_orders.append(order)
            
            # Determine which market this order came from and log the quantity
            if order['ticker'].endswith('_M'):
                wac_data[base_ticker]['MarketQuantities']['Main Market'] += quantity_to_take
            elif order['ticker'].endswith('_A'):
                wac_data[base_ticker]['MarketQuantities']['Alternative Market'] += quantity_to_take
            elif order['ticker'] in ['CRZY', 'TAME', 'BBSN']:  # Check for Normal market
                wac_data[base_ticker]['MarketQuantities']['Normal'] += quantity_to_take

            # Update WAC calculation for this stock
            wac_data[base_ticker]['Quantity'] += quantity_to_take
            wac_data[base_ticker]['WAC'] = (wac_data[base_ticker]['WAC'] * (wac_data[base_ticker]['Quantity'] - quantity_to_take) + (quantity_to_take * price)) / wac_data[base_ticker]['Quantity']

    # Print contributing orders for WAC calculation for debugging of WAC accuract
    # print("Orders contributing to WAC calculation:")
    # for order in contributing_orders:
    #     print(f"Order: {order}")


        # Decision based on WAC and tender offer price
    if total_quantity >= offer_quantity and (action == 'BUY' and wac_data[base_ticker]['WAC'] > offer_price) or (action == 'SELL' and wac_data[base_ticker]['WAC'] < offer_price):
        # Calculate potential gain
        if action == 'BUY':
            potential_gain = (wac_data[base_ticker]['WAC'] - offer_price) * total_quantity
        else:  # action == 'SELL'
            potential_gain = (offer_price - wac_data[base_ticker]['WAC']) * total_quantity
        
        print(f"Accept. Potential Gain: {potential_gain:.2f}")
        return "Accept", total_quantity, wac_data[base_ticker]['WAC'], wac_data[base_ticker]['MarketQuantities']

    elif total_quantity < offer_quantity and (action == 'BUY' and wac_data[base_ticker]['WAC'] > offer_price) or (action == 'SELL' and wac_data[base_ticker]['WAC'] < offer_price):
        # Calculate potential gain with available quantity
        if action == 'BUY':
            potential_gain = (wac_data[base_ticker]['WAC'] - offer_price) * total_quantity
        else:  # action == 'SELL'
            potential_gain = (offer_price - wac_data[base_ticker]['WAC']) * total_quantity
        print(f"Insufficient quantity sourced ({total_quantity} < {offer_quantity}).")
        print(f"Current WAC: {wac_data[base_ticker]['WAC']:.2f}, Potential Gain with available quantity: {potential_gain:.2f}")
        return "Neutral", total_quantity, wac_data[base_ticker]['WAC'], wac_data[base_ticker]['MarketQuantities']

    elif total_quantity < offer_quantity and (action == 'BUY' and wac_data[base_ticker]['WAC'] < offer_price) or (action == 'SELL' and wac_data[base_ticker]['WAC'] > offer_price):            
        print(f"Decline reason: Insufficient quantity sourced ({total_quantity} < {offer_quantity}) and price unfavorable")
        print(f"Current WAC: {wac_data[base_ticker]['WAC']:.2f}")
        return "Decline", total_quantity, wac_data[base_ticker]['WAC'], wac_data[base_ticker]['MarketQuantities']

    elif action == 'BUY' and wac_data[base_ticker]['WAC'] < offer_price:
        potential_loss_pct = ((offer_price - wac_data[base_ticker]['WAC']) / offer_price) * 100
        print(f"Decline reason: Price unfavorable. WAC: {wac_data[base_ticker]['WAC']:.2f}, Offer Price: {offer_price:.2f}, Potential loss: -{potential_loss_pct:.2f}%")
        return "Decline", total_quantity, wac_data[base_ticker]['WAC'], wac_data[base_ticker]['MarketQuantities']

    elif action == 'SELL' and wac_data[base_ticker]['WAC'] > offer_price:
        potential_loss_pct = ((wac_data[base_ticker]['WAC'] - offer_price) / offer_price) * 100
        print(f"Decline reason: Price unfavorable. WAC: {wac_data[base_ticker]['WAC']:.2f}, Offer Price: {offer_price:.2f}, Potential loss: -{potential_loss_pct:.2f}%")
        return "Decline", total_quantity, wac_data[base_ticker]['WAC'], wac_data[base_ticker]['MarketQuantities']


def main():
    accepted_tender_expiry_time = None  # Variable to hold the expiration time of the accepted tender

    with requests.Session() as s:
        s.headers.update(API_KEY)
        
        tick = get_tick(s)
        
        while tick > 5 and tick < 295 and not shutdown:
            clear_screen()
            print(f"Tick: {tick}")

            # Check for expiration before proceeding with an accepted tender
            if accepted_tender_expiry_time is not None and accepted_tender_expiry_time < tick:
                print("The tender has expired.")
                accepted_tender_expiry_time = None  # Reset since it's expired
            
            # Get and filter tender offers only if no active accepted tender exists
            if accepted_tender_expiry_time is None:  
                tender_offers = filter_tender_offers(get_tender(s))
                if len(tender_offers) == 0:
                    print("No valid tender offers available.")
                    sleep(1)
                    tick = get_tick(s)
                    continue
                
                # Use only the most recent tender offer
                current_tender = tender_offers[0]
                accepted_tender_expiry_time = current_tender['expires']  # Store expiration time
            
            else:
                pass
                # current_tender = {
                #     'ticker': current_tender['ticker'], 
                #     'quantity': current_tender['quantity'], 
                #     'price': current_tender['price'], 
                #     'action': current_tender['action']
                # }
            
            tender_ticker = current_tender['ticker'] 
            
            # Get order books for both stocks separately (for both markets)
            order_books = {
                'CRZY_M': ticker_bid_ask(s, 'CRZY_M'),
                'CRZY_A': ticker_bid_ask(s, 'CRZY_A'),
                'CRZY': ticker_bid_ask(s, 'CRZY'),
                'TAME_M': ticker_bid_ask(s, 'TAME_M'),
                'TAME_A': ticker_bid_ask(s, 'TAME_A'),
                'TAME': ticker_bid_ask(s, 'TAME'),
                'BBSN': ticker_bid_ask(s, 'BBSN'),
            }

            # Determine which stock's order book to use based on the tender ticker
            relevant_order_book = None
            
            if tender_ticker == 'CRZY_M':
                relevant_order_book = order_books['CRZY_M']
            elif tender_ticker == 'CRZY_A':
                relevant_order_book = order_books['CRZY_A']
            elif tender_ticker == 'CRZY':
                relevant_order_book = order_books['CRZY']
            elif tender_ticker == 'TAME_M':
                relevant_order_book = order_books['TAME_M']
            elif tender_ticker == 'TAME_A':
                relevant_order_book = order_books['TAME_A']
            elif tender_ticker == 'TAME':
                relevant_order_book = order_books['TAME']
            elif tender_ticker == "BBSN":
                relevant_order_book = order_books['BBSN']

            
            if relevant_order_book is None:
                print(f"Unknown stock for ticker: {tender_ticker}")
                sleep(1)
                continue
            
            print("-------------Tender Details----------------")
            pprint(current_tender)
            
            print("----------------Decision------------------")
            decision, total_quantity, wac, market_quantities = calculate_wac_and_liquidity(order_books=order_books, tender_offer=[current_tender])
            
            print(f"Decision: {decision}")
            # Include market information in decision output
            if tender_ticker.endswith('_M'):
                market_type = "Main Market"
            elif tender_ticker.endswith('_A'):
                market_type = "Alternative Market"
            else:
                market_type = "Normal"

           
            
            if decision == "Accept":
                print(f"Total Quantity Sourced: {total_quantity}, WAC: {wac:.2f}")
                print(f"Market Quantities: {market_quantities}")
                print(f"Market to Reverse Trade: {market_type}")
                
                # Optionally reset or keep the accepted tender depending on your logic.
                
            sleep(1)

            tick = get_tick(s)

if __name__ == '__main__':
    while True:
        clear_screen()
        signal.signal(signal.SIGINT, signal_handler)
        main()
        print("restarting..")
        sleep(2)