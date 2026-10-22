"""
E-mail channel behind a small provider interface (docs/architecture.md:
"email first; Teams/Telegram/Slack pluggable later"). Application code
calls `get_email_sender().send(message)`; only this module knows SMTP.
"""
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailNotConfiguredError(Exception):
    """The channel is switched off or has no SMTP host — the message is
    recorded as skipped rather than sent."""


class EmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Raises on failure; `EmailNotConfiguredError` when not set up."""


class SmtpEmailSender(EmailSender):
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: EmailMessage) -> None:
        s = self.settings
        mime = MimeMessage()
        mime["From"] = s.smtp_from_address
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        if message.html:
            mime.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_use_tls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(mime)


class DisabledEmailSender(EmailSender):
    def __init__(self, reason: str):
        self.reason = reason

    def send(self, message: EmailMessage) -> None:
        logger.info("E-mail not sent (%s): to=%s subject=%r", self.reason, message.to, message.subject)
        raise EmailNotConfiguredError(self.reason)


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    settings = settings or get_settings()
    if not settings.notifications_email_enabled:
        return DisabledEmailSender("NOTIFICATIONS_EMAIL_ENABLED is false")
    if not settings.smtp_host:
        return DisabledEmailSender("SMTP_HOST is not set")
    return SmtpEmailSender(settings)
