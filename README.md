# Dialed Gum — MAP Tracker

Monitors Amazon listings for Dialed Gum products and alerts you (email + SMS) when any reseller prices below your Minimum Advertised Price.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your products and MAP prices
#    Edit config.json — add your ASINs and MAP prices

# 3. Set up credentials
cp .env.example .env
#    Fill in your email (Gmail App Password) and/or Twilio credentials

# 4. Run a manual check
python run_check.py

# 5. Schedule twice-daily checks (8 AM / 8 PM)
bash setup_cron.sh
```

## Configuration

### config.json

| Field | Description |
|-------|-------------|
| `products[].asin` | Amazon ASIN for each Dialed Gum SKU |
| `products[].map_price` | Minimum Advertised Price for that SKU |
| `authorized_resellers` | List of reseller names you're tracking |

### Notifications

**Email** — Uses SMTP (Gmail works with an [App Password](https://support.google.com/accounts/answer/185833)). Set credentials in `.env`.

**SMS** — Uses [Twilio](https://www.twilio.com/). Free trial gives you a number and credits. Set credentials in `.env`.

### Optional: Rainforest API

Direct Amazon scraping can be unreliable. For production use, set `RAINFOREST_API_KEY` in `.env` to use the [Rainforest API](https://www.rainforestapi.com/) instead — much more reliable and returns all third-party seller offers.

## What You Get

- Twice-daily price checks across all your ASINs
- Email with a full violation table (product, seller, price vs MAP, links)
- SMS text alert with a summary
- CSV log of all violations (`violations.csv`) for historical tracking

## Adding Products

Add entries to the `products` array in `config.json`:

```json
{
  "name": "Dialed Gum 10-Pack Spearmint",
  "asin": "B0XXXXXXXXX",
  "map_price": 24.99
}
```
