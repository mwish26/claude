"""MAP compliance checker — main orchestration module."""

import csv
import json
import logging
import os
import time
import random
from datetime import datetime, timezone
from pathlib import Path

from .scraper import scrape_amazon_offers, fetch_offers_rainforest, Offer
from .notifier import notify_violations, notify_all_clear

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        cfg = json.load(f)

    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: dict) -> None:
    """Override config values with environment variables when set."""
    email = cfg["notifications"]["email"]
    if os.getenv("SMTP_HOST"):
        email["smtp_host"] = os.environ["SMTP_HOST"]
    if os.getenv("SMTP_PORT"):
        email["smtp_port"] = int(os.environ["SMTP_PORT"])
    if os.getenv("SENDER_EMAIL"):
        email["sender_email"] = os.environ["SENDER_EMAIL"]
    if os.getenv("SENDER_PASSWORD"):
        email["sender_password"] = os.environ["SENDER_PASSWORD"]
    if os.getenv("EMAIL_RECIPIENTS"):
        email["recipients"] = os.environ["EMAIL_RECIPIENTS"].split(",")

    sms = cfg["notifications"]["sms"]
    if os.getenv("TWILIO_ACCOUNT_SID"):
        sms["account_sid"] = os.environ["TWILIO_ACCOUNT_SID"]
    if os.getenv("TWILIO_AUTH_TOKEN"):
        sms["auth_token"] = os.environ["TWILIO_AUTH_TOKEN"]
    if os.getenv("TWILIO_FROM_NUMBER"):
        sms["from_number"] = os.environ["TWILIO_FROM_NUMBER"]
    if os.getenv("SMS_RECIPIENTS"):
        sms["to_numbers"] = os.environ["SMS_RECIPIENTS"].split(",")


def check_map_compliance(config: dict) -> list[dict]:
    """Fetch offers for all products and return any MAP violations."""
    products = config["products"]
    rainforest_key = os.getenv("RAINFOREST_API_KEY", "")
    all_violations: list[dict] = []
    total_offers = 0

    for product in products:
        asin = product["asin"]
        name = product["name"]
        map_price = product["map_price"]

        logger.info("Checking %s (ASIN: %s, MAP: $%.2f)", name, asin, map_price)

        if rainforest_key:
            offers = fetch_offers_rainforest(asin, name, rainforest_key)
        else:
            offers = scrape_amazon_offers(asin, name)

        total_offers += len(offers)
        logger.info("  Found %d offer(s)", len(offers))

        for offer in offers:
            if offer.price < map_price:
                violation = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "product_name": offer.product_name,
                    "asin": offer.asin,
                    "seller_name": offer.seller_name,
                    "price": offer.price,
                    "map_price": map_price,
                    "url": offer.url,
                }
                all_violations.append(violation)
                logger.warning(
                    "  VIOLATION: %s selling at $%.2f (MAP $%.2f)",
                    offer.seller_name, offer.price, map_price,
                )

        if len(products) > 1:
            time.sleep(random.uniform(2, 5))

    return all_violations, total_offers


def log_violations(violations: list[dict], log_path: str) -> None:
    """Append violations to a CSV log file."""
    if not violations:
        return

    file_exists = Path(log_path).exists()
    fieldnames = ["timestamp", "product_name", "asin", "seller_name", "price", "map_price", "url"]

    with open(log_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(violations)

    logger.info("Logged %d violation(s) to %s", len(violations), log_path)


def run() -> None:
    """Run a single MAP compliance check cycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("=== Dialed Gum MAP Compliance Check ===")
    config = load_config()

    violations, total_offers = check_map_compliance(config)

    if violations:
        log_violations(violations, config.get("violation_log", "violations.csv"))
        notify_violations(config, violations)
        logger.info("Check complete: %d violation(s) found.", len(violations))
    else:
        notify_all_clear(config, len(config["products"]), total_offers)
        logger.info("Check complete: all prices at or above MAP.")
