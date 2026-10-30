"""E-mail notifications to the site owner. Sending never blocks or fails a request."""
from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
from threading import Thread

log = logging.getLogger("uvicorn.error")


def configured():
    return all(os.environ.get(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_EMAIL"))


def _send(subject, body, to=None, reply_to=None):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ.get("SMTP_FROM") or os.environ["SMTP_USER"]
    message["To"] = to or os.environ["NOTIFY_EMAIL"]
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=context)
                server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                server.send_message(message)
    except Exception:  # noqa: BLE001 - a failed notification must not break the request
        log.exception("notification e-mail failed")


def send(subject, body):
    """Notify the site owner in the background. Returns False when SMTP is not configured."""
    if not configured():
        log.warning("SMTP not configured; skipped notification: %s", subject)
        return False
    Thread(target=_send, args=(subject, body), daemon=True).start()
    return True


def send_customer(to, subject, body):
    """Mail a customer in the background; replies go to the owner's address."""
    if not configured():
        log.warning("SMTP not configured; skipped customer mail: %s", subject)
        return False
    Thread(target=_send, args=(subject, body, to, os.environ["NOTIFY_EMAIL"]), daemon=True).start()
    return True


def base_url():
    return (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
