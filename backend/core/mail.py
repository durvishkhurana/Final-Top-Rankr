"""Outgoing email. Without an SMTP host the message is written to the log instead,
which is enough for development and for links an administrator passes on by hand."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger("mail")


def _deliver(message: EmailMessage) -> None:
    s = get_settings()
    if not s.smtp_host:
        log.warning("SMTP is not configured; email to %s:\n%s\n%s", message["To"],
                    message["Subject"], message.get_content())
        return
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(message)


async def send(to: str, subject: str, body: str) -> None:
    """Sends in a thread. A failure is logged, never raised: the request that caused
    the email must not fail because the mail server is down."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = get_settings().smtp_from, to, subject
    message.set_content(body)
    try:
        await asyncio.to_thread(_deliver, message)
    except (OSError, smtplib.SMTPException):
        log.exception("sending email to %s failed", to)
