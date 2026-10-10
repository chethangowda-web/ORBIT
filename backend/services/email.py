"""
Outbound email (SMTP).

Optional channel next to Google Chat. Disabled unless SMTP_HOST and EMAIL_FROM are configured.
Sending never raises: a mail outage must not break the task change that triggered it.
"""

import asyncio
import html
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from config import settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_enabled() -> bool:
    return bool(settings.SMTP_HOST and settings.EMAIL_FROM)


def is_valid_address(address: str | None) -> bool:
    if not address or "\n" in address or "\r" in address:
        return False
    return bool(_EMAIL_RE.match(parseaddr(address)[1]))


def _single_line(value: str, limit: int = 200) -> str:
    """Header values must never contain line breaks (header injection)."""
    return re.sub(r"[\r\n]+", " ", value).strip()[:limit]


def build_message(to: str, subject: str, text: str, link: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.APP_NAME, parseaddr(settings.EMAIL_FROM)[1]))
    msg["To"] = parseaddr(to)[1]
    msg["Subject"] = _single_line(subject)
    body = text + (f"\n\nOpen in ORBIT: {link}" if link else "")
    msg.set_content(body)
    escaped = "<br>".join(html.escape(line) for line in text.splitlines())
    button = f'<p><a href="{html.escape(link, quote=True)}">Open in ORBIT</a></p>' if link else ""
    msg.add_alternative(f"<html><body style=\"font-family:sans-serif\"><p>{escaped}</p>{button}</body></html>", subtype="html")
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    host, port, mode = settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_SECURITY.lower()
    timeout = settings.SMTP_TIMEOUT
    if mode == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(host, port, timeout=timeout)
    with smtp:
        if mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_email(to: str, subject: str, text: str, link: str | None = None) -> tuple[str, str | None]:
    """Returns (status, error): ``sent`` only after the server accepted the message."""
    if not email_enabled():
        return "skipped", "Email is not configured"
    if not is_valid_address(to):
        return "skipped", "Recipient has no valid email address"
    try:
        msg = build_message(to, subject, text, link)
        await asyncio.wait_for(asyncio.to_thread(_send_blocking, msg), timeout=settings.SMTP_TIMEOUT + 5)
        return "sent", None
    except Exception as exc:
        logger.warning("Email to %s failed: %s", to, exc)
        return "failed", str(exc)[:500]
