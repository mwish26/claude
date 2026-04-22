import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

logger = logging.getLogger(__name__)


def send_email(config: dict, subject: str, body_html: str, body_text: str) -> bool:
    """Send an email alert via SMTP."""
    email_cfg = config["notifications"]["email"]
    if not email_cfg.get("enabled"):
        return False
    if not email_cfg.get("sender_email") or not email_cfg.get("recipients"):
        logger.warning("Email enabled but sender_email or recipients not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_cfg["sender_email"]
    msg["To"] = ", ".join(email_cfg["recipients"])
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as server:
            server.starttls()
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.sendmail(
                email_cfg["sender_email"],
                email_cfg["recipients"],
                msg.as_string(),
            )
        logger.info("Email sent to %s", email_cfg["recipients"])
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def send_sms(config: dict, message: str) -> bool:
    """Send SMS via Twilio."""
    sms_cfg = config["notifications"]["sms"]
    if not sms_cfg.get("enabled"):
        return False
    if not sms_cfg.get("account_sid") or not sms_cfg.get("auth_token"):
        logger.warning("SMS enabled but Twilio credentials not configured")
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sms_cfg['account_sid']}/Messages.json"
    sent = False

    for number in sms_cfg["to_numbers"]:
        try:
            resp = requests.post(
                url,
                data={
                    "From": sms_cfg["from_number"],
                    "To": number,
                    "Body": message,
                },
                auth=(sms_cfg["account_sid"], sms_cfg["auth_token"]),
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("SMS sent to %s", number)
            sent = True
        except requests.RequestException as e:
            logger.error("Failed to send SMS to %s: %s", number, e)

    return sent


def format_violation_alert(violations: list[dict]) -> tuple[str, str, str]:
    """Build subject, HTML body, and plain-text body for a MAP violation alert.

    Returns (subject, html, text).
    """
    count = len(violations)
    subject = f"MAP Violation Alert: {count} violation{'s' if count != 1 else ''} detected - Dialed Gum"

    text_lines = [f"MAP VIOLATION ALERT — {count} violation{'s' if count != 1 else ''}\n"]
    html_lines = [
        "<h2 style='color:#d32f2f;'>MAP Violation Alert</h2>",
        f"<p><strong>{count} violation{'s' if count != 1 else ''}</strong> detected for Dialed Gum products.</p>",
        "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse;'>",
        "<tr style='background:#f5f5f5;'>"
        "<th>Product</th><th>Seller</th><th>Listed Price</th><th>MAP</th><th>Difference</th><th>Link</th></tr>",
    ]

    for v in violations:
        diff = v["map_price"] - v["price"]
        text_lines.append(
            f"  {v['product_name']}\n"
            f"    Seller: {v['seller_name']}\n"
            f"    Price: ${v['price']:.2f} (MAP: ${v['map_price']:.2f}, ${diff:.2f} under)\n"
            f"    Link: {v['url']}\n"
        )
        color = "#d32f2f" if diff > 2 else "#f57c00"
        html_lines.append(
            f"<tr>"
            f"<td>{v['product_name']}</td>"
            f"<td>{v['seller_name']}</td>"
            f"<td style='color:{color};font-weight:bold;'>${v['price']:.2f}</td>"
            f"<td>${v['map_price']:.2f}</td>"
            f"<td>-${diff:.2f}</td>"
            f"<td><a href='{v['url']}'>View</a></td>"
            f"</tr>"
        )

    html_lines.append("</table>")
    text = "\n".join(text_lines)
    html = "\n".join(html_lines)

    sms_text = f"MAP ALERT: {count} Dialed Gum violation{'s' if count != 1 else ''}. "
    for v in violations[:3]:
        sms_text += f"{v['seller_name']}: ${v['price']:.2f} (MAP ${v['map_price']:.2f}). "
    if count > 3:
        sms_text += f"+ {count - 3} more. Check email for details."

    return subject, html, text, sms_text


def notify_violations(config: dict, violations: list[dict]) -> None:
    """Send all configured notifications for MAP violations."""
    if not violations:
        logger.info("No violations — no notifications sent.")
        return

    subject, html, text, sms_text = format_violation_alert(violations)
    send_email(config, subject, html, text)
    send_sms(config, sms_text)


def notify_all_clear(config: dict, product_count: int, offer_count: int) -> None:
    """Optional: send a short confirmation that everything looks good."""
    msg = f"Dialed Gum MAP check complete. {product_count} products, {offer_count} offers checked. No violations."
    logger.info(msg)
