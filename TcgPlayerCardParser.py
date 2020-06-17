"""
Parses TCGPlayer for cards under a certain value.
Configurable to allow for searches over a certain value.
"""
import os
from multiprocessing import Pool, cpu_count
from functools import partial
import operator
from typing import Callable, List, Union, NamedTuple

import pandas
import grequests
from bs4 import BeautifulSoup

CardOffer = NamedTuple('CardOffer', [('card_name', str), ('card_price', float)])


def sanitize_card_text(card_text: str) -> CardOffer:
    """
    Parses all the text in the card offer to make it cleaner.
    Unfortunately the parsing is quite a bit ugly, and prone to breaking if they were to change anything on their site.
    :param card_text: Card Offer Text
    :return: Dict{"product_name":card_name,}
    """
    result = card_text[card_text.find('{') + 1:card_text.find('}')]
    result.replace(' ', '')
    result.replace('\n', '')
    lines = result.split(',')
    card_dict = {}
    for line in lines:
        key_val = line.split(':')
        if len(key_val) != 2:
            raise RuntimeError("Invalid Split Occured")
        card_dict[key_val[0].replace(" ", '').replace('\r\n', '')] = key_val[1]
    return CardOffer(card_name=card_dict['"product_name"'], card_price=float(card_dict['"price"'].replace("\"", '')))


def find_matching_offers(offers: List[str], value: float, *,
                         comparison: Callable[[float, float], bool] = operator.lt) -> List[CardOffer]:
    """
    :param offers: Offers to compare.
    :param value: Value to compare against.
    :param comparison: Comparison function.
    :return: Return all offers that compare truthfully
    """
    within_price_range = []
    for offer in offers:
        card_offer = sanitize_card_text(offer)
        if comparison(card_offer.card_price, value):
            within_price_range.append(card_offer)
    return within_price_range


def get_request_url(page_number, rarity, color):
    return 'https://shop.tcgplayer.com/magic/product/show?newSearch=false&Color={color}&Type=Cards&Rarity={rarity}&orientation=list&PageNumber={page}'.format(
        page=page_number, rarity=rarity, color=color)


def scrape_page(retrieved_page, value, *,
                comparison: Callable[[float, float], bool] = operator.lt) -> Union[List[CardOffer], None]:
    """
    :param retrieved_page: Http response page.
    :param value: comparison value.
    :param comparison:  How to compare card price to the given value. Lt/Gt/EQ.
    :return: None if invalid page_read.
    """
    soup = BeautifulSoup(retrieved_page.content, 'html.parser')
    cards = soup.find_all('div', class_="product")
    try:
        offers = [card.find('div', class_='product__offers').find('script').get_text() for card in cards]
    except AttributeError:
        return None
    return find_matching_offers(offers=offers, value=value, comparison=comparison)


def main(rarity: str, color: str, value: float, comparison: Callable[[float, float], bool]) -> None:
    """
    Controls looping logic and writes the output to file.
    :param rarity: Card Rarity. Common/Uncommon/Rare/Mythic ...
    :param color: Card color->red/blue/green/black/white/colorless.
    :param value: Dollar value to compare to.
    :param comparison:  How to compare card price to the given value. Lt/Gt/EQ.
    :return:
    """
    all_matching_cards = set()
    # tcgplayer fails after page 1000
    rs = (grequests.get(get_request_url(page_num, rarity, color)) for page_num in range(1, 1001))
    responses = grequests.map(rs)
    print('Recieved responses')
    successful_responses = [response for response in responses if response.status_code == 200]
    scraper = partial(scrape_page, value=value, comparison=comparison)
    with Pool(processes=cpu_count() - 1) as pool:
        data = pool.map(scraper, successful_responses)
        for listy in data:
            if listy:
                for offer in listy:
                    all_matching_cards.add(offer.card_name.strip().replace('\"', ''))

    all_matching_cards_df = pandas.DataFrame({"names": list(all_matching_cards)})
    save_path = os.path.join(os.path.curdir, f'foundcards_{color}_{rarity}.csv')
    all_matching_cards_df.to_csv(save_path)


if __name__ == '__main__':
    RARITY = 'Common'
    COLOR = 'Green'
    COMPARISON = operator.lt  # must take two float values
    import time
    start = time.time()
    main(rarity=RARITY, color=COLOR, value=0.06, comparison=COMPARISON)
    print(time.time() - start)
