"""
Parses TCGPlayer for cards under a certain value.
Configurable to allow for searches over a certain value.
"""
import time
import operator
from collections import namedtuple
from typing import Callable, Dict, Union

import pandas
import requests
from bs4 import BeautifulSoup

CardOffer = namedtuple('CardOffer', ['card_name', 'card_price'])


def sanitize_card_text(card_text):
    """
    Parses all the text in the card offer to make it cleaner.
    Unfortunately the parsing is quite a bit ugly, and prone to breaking if they were to change XYZ on their site.
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


def find_matching_offers(offers, value, *, comparison=operator.lt):
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
            print(card_offer.card_name, card_offer.card_price)
            within_price_range.append(card_offer)
    return within_price_range


def soupify_page(url):
    """
    Performs a request on a page and then transforms it into a soup document,
    :param url: Url to request.
    :return: Soup document.
    """
    retrieved_page = requests.get(url)
    return BeautifulSoup(retrieved_page.content, 'html.parser')


def scrape_page(page_number: int, color: str, value: float, rarity: str = 'Common', *,
                comparison: Callable[[float, float], bool] = operator.lt) -> Union[Dict, None]:
    """
    :param page_number: Results page number.
    :param color: Card color->red/blue/green/black/white/colorless
    :param value: comparison value.
    :param rarity: Card Rarity. Common/Uncommon/Rare/Mythic ...
    :param comparison:  How to compare card price to the given value. Lt/Gt/EQ
    :return: None if invalid page_read
    """
    url = 'https://shop.tcgplayer.com/magic/product/show?newSearch=false&Color={color}&Type=Cards&Rarity={rarity}&orientation=list&PageNumber={page}'.format(
        page=page_number, rarity=rarity, color=color)
    soup = soupify_page(url)
    cards = soup.find_all('div', class_="product")
    try:
        offers = [card.find('div', class_='product__offers').find('script').get_text() for card in cards]
    except AttributeError:
        print('Page {url} did not have any offers'.format(url=url))
        return None
    return find_matching_offers(offers=offers, value=value, comparison=comparison)


def main(rarity, color, comparison):
    all_matching_cards = {'names': [],
                          'prices': []
                          }
    for page_number in range(1000):  # Tcgplayer page breaks on page 1000
        scraped_page = scrape_page(page_number=page_number, color=color, value=0.06, rarity=rarity,
                                   comparison=comparison)
        if scraped_page is None:
            time.sleep(3)  # Retry once
            scraped_page = scrape_page(page_number=page_number, color=color, value=0.06, rarity=rarity,
                                       comparison=comparison)
            if scraped_page is None:
                print("Multiple requests to page failed. Saving retrieved results to file and terminating.")
                break
        for offer in scraped_page:
            all_matching_cards['names'].append(offer.card_name)
            all_matching_cards['prices'].append(offer.card_price)
    all_matching_cards_df = pandas.DataFrame(all_matching_cards)
    all_matching_cards_df.to_csv(f'./foundcards_{color}_{rarity}.csv')


if __name__ == '__main__':
    RARITY = 'Common'
    COLOR = 'Green'
    COMPARISON = operator.lt  # must take two float values
    main(rarity=RARITY, color=COLOR, comparison=COMPARISON)
