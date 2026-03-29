"""Email notification sender for power status events."""
import os
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict

from .config import Config  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not available. Environment variables must be set manually.")

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends power status email notifications."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config
        self.last_notification_time: Optional[float] = None
        self._load_settings()

    def _load_settings(self) -> None:
        """Load (or reload) settings from config file or environment variables."""
        if self.config:
            try:
                self.config.load()
            except Exception as e:
                logger.warning(f"Could not reload config: {e}")

            self.enabled = bool(self.config.get("email.enabled", False))
            self.rate_limit_seconds = int(self.config.get("email.rate_limit_seconds", 300))
            self.smtp_server = self.config.get("email.smtp_server", "smtp.gmail.com")
            self.smtp_port = int(self.config.get("email.smtp_port", 587))
            self.smtp_username = self.config.get("email.smtp_username", "") or ""
            self.smtp_password = self.config.get("email.smtp_password", "") or ""
            self.email_from = self.config.get("email.from", self.smtp_username) or self.smtp_username

            to_val = self.config.get("email.to", "")
            if isinstance(to_val, list):
                self.emails_to = [e.strip() for e in to_val if str(e).strip()]
            else:
                self.emails_to = [e.strip() for e in str(to_val).split(",") if e.strip()]
        else:
            self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
            self.rate_limit_seconds = int(os.getenv("EMAIL_RATE_LIMIT_SECONDS", "300"))
            self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
            self.smtp_username = os.getenv("SMTP_USERNAME", "") or ""
            self.smtp_password = os.getenv("SMTP_PASSWORD", "") or ""
            self.email_from = os.getenv("EMAIL_FROM", self.smtp_username) or self.smtp_username
            to_env = os.getenv("EMAIL_TO", "")
            self.emails_to = [e.strip() for e in to_env.split(",") if e.strip()]

        if not self.enabled:
            logger.info("Email notifications are disabled")
        elif not self.smtp_username or not self.smtp_password:
            logger.warning("Email enabled but SMTP username/password missing")
            self.enabled = False
        elif not self.emails_to:
            logger.warning("Email enabled but no recipients configured")
            self.enabled = False
        else:
            logger.info(f"Email ready — {len(self.emails_to)} recipient(s): {', '.join(self.emails_to)}")

    def _check_rate_limit(self) -> bool:
        if self.last_notification_time is None:
            return True
        elapsed = time.time() - self.last_notification_time
        if elapsed < self.rate_limit_seconds:
            logger.info(f"Rate limit active — next email in {self.rate_limit_seconds - elapsed:.0f}s")
            return False
        return True

    def _send_smtp(self, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ", ".join(self.emails_to)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.smtp_username, self.emails_to, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to: {', '.join(self.emails_to)}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed — check username/password/app-password: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connection failed — check server/port: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_power_status_notification(
        self,
        states: Dict[str, Optional[int]],
        event_time: float
    ) -> bool:
        """
        Send a power status email showing the current state of all inputs.

        Args:
            states: dict with keys 'eb', 'gen1', 'gen2', 'gen3' and values 0/1/None
            event_time: unix timestamp of the triggering event
        """
        self._load_settings()

        if not self.enabled:
            logger.debug("Email notifications disabled — skipping")
            return False

        if not self._check_rate_limit():
            return False

        def fmt(val: Optional[int]) -> str:
            if val is None:
                return "UNKNOWN"
            return "ON" if val == 1 else "OFF"

        eb   = fmt(states.get('eb'))
        gen1 = fmt(states.get('gen1'))
        gen2 = fmt(states.get('gen2'))
        gen3 = fmt(states.get('gen3'))

        event_dt = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d %H:%M:%S")
        subject = f"Power Cut Information - {event_dt}"

        body = (
            "Greetings!!\n\n"
            "Sub: Power Cut Information -Reg\n\n"
            "Greetings!!\n\n"
            f"EB Power Is Turned {eb:<7} ( ON/OFF)\n"
            f"DG - 1 is Switched {gen1:<7} ( ON/OFF)\n"
            f"DG-2 is Switched   {gen2:<7} ( ON/OFF)\n"
            f"DG -3 is Switched  {gen3:<7} ( ON/OFF)\n\n"
            "Thank you"
        )

        try:
            success = self._send_smtp(subject, body)
            if success:
                self.last_notification_time = time.time()
            return success
        except Exception as e:
            logger.error(f"Error sending power status email: {e}", exc_info=True)
            return False
