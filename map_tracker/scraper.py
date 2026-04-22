import re
import time
import random
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

AMAZON_BASE = "https://www.amazon.com/dp/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


@dataclass
class Offer:
    seller_name: str
    price: float
    asin: str
    product_name: str
    url: str


def _parse_price(text: str) -> float | None:
    match = re.search(r"\$?([\d,]+\.?\d*)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def scrape_amazon_offers(asin: str, product_name: str) -> list[Offer]:
    """Scrape offers for a product from its Amazon offers page."""
    url = f"https://www.amazon.com/gp/offer-listing/{asin}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }

    offers: list[Offer] = []
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        listing_rows = soup.select(".olpOffer")
        for row in listing_rows:
            price_el = row.select_one(".olpOfferPrice")
            seller_el = row.select_one(".olpSellerName")
            if not price_el:
                continue

            price = _parse_price(price_el.get_text())
            if price is None:
                continue

            seller = "Unknown"
            if seller_el:
                seller = seller_el.get_text(strip=True)

            offers.append(Offer(
                seller_name=seller,
                price=price,
                asin=asin,
                product_name=product_name,
                url=f"{AMAZON_BASE}{asin}",
            ))

        if not offers:
            offers = _scrape_buybox(asin, product_name, headers)

    except requests.RequestException as e:
        logger.error("Failed to scrape ASIN %s: %s", asin, e)

    return offers


def _scrape_buybox(asin: str, product_name: str, headers: dict) -> list[Offer]:
    """Fallback: scrape the main product page for the Buy Box price/seller."""
    url = f"{AMAZON_BASE}{asin}"
    offers: list[Offer] = []
    try:
        time.sleep(random.uniform(1, 3))
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        price = None
        for selector in ["#priceblock_ourprice", "#priceblock_dealprice",
                         ".a-price .a-offscreen", "#corePrice_feature_div .a-offscreen"]:
            el = soup.select_one(selector)
            if el:
                price = _parse_price(el.get_text())
                if price:
                    break

        seller = "Amazon.com"
        seller_el = soup.select_one("#sellerProfileTriggerId")
        if seller_el:
            seller = seller_el.get_text(strip=True)

        if price:
            offers.append(Offer(
                seller_name=seller,
                price=price,
                asin=asin,
                product_name=product_name,
                url=url,
            ))
    except requests.RequestException as e:
        logger.error("Buybox fallback failed for ASIN %s: %s", asin, e)

    return offers


def fetch_offers_rainforest(asin: str, product_name: str, api_key: str) -> list[Offer]:
    """Use the Rainforest API for reliable Amazon data (paid service)."""
    url = "https://api.rainforestapi.com/request"
    params = {
        "api_key": api_key,
        "type": "offers",
        "amazon_domain": "amazon.com",
        "asin": asin,
    }

    offers: list[Offer] = []
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for offer in data.get("offers", []):
            price = offer.get("price", {}).get("value")
            seller = offer.get("seller", {}).get("name", "Unknown")
            if price is not None:
                offers.append(Offer(
                    seller_name=seller,
                    price=float(price),
                    asin=asin,
                    product_name=product_name,
                    url=f"{AMAZON_BASE}{asin}",
                ))
    except requests.RequestException as e:
        logger.error("Rainforest API failed for ASIN %s: %s", asin, e)

    return offers
