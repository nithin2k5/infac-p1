"""Email notification sender for power outage events."""
import os
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict, Any

from .config import Config  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not available. Environment variables must be set manually.")

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends power outage summary email notifications."""

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
            logger.error(f"SMTP auth failed — check username/password/app-password: {e}")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connection failed — check server/port: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @staticmethod
    def _fmt_time(ts: Optional[float]) -> str:
        """Format a unix timestamp as DD/MM/YYYY HH:MM, or '---' if None."""
        if ts is None:
            return "---"
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _fmt_duration(t_on: Optional[float], t_off: Optional[float]) -> str:
        """Format duration between two timestamps as H:MM Hrs, or 'Ongoing' / '---'."""
        if t_on is None:
            return "---"
        if t_off is None:
            return "Ongoing"
        secs = max(t_off - t_on, 0)
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        return f"{h}:{m:02d} Hrs"

    def send_outage_notification(
        self,
        outage: Dict[str, Any],
        bypass_rate_limit: bool = False
    ) -> bool:
        """
        Send a power outage summary email.

        outage dict keys:
            eb_off_time   : float or None  — when EB went OFF
            eb_on_time    : float or None  — when EB came back ON (None = still cut)
            gen1/gen2/gen3: {'on': float|None, 'off': float|None}
            reason        : str or None    — captured reason text
        """
        self._load_settings()

        if not self.enabled:
            logger.debug("Email notifications disabled — skipping")
            return False

        if not bypass_rate_limit and not self._check_rate_limit():
            return False

        eb_cut    = self._fmt_time(outage.get('eb_off_time'))
        eb_resume = self._fmt_time(outage.get('eb_on_time'))
        eb_total  = self._fmt_duration(outage.get('eb_off_time'), outage.get('eb_on_time'))

        dg_lines = []
        for idx, key in enumerate(['gen1', 'gen2', 'gen3'], start=1):
            g = outage.get(key, {})
            on_t  = g.get('on')
            off_t = g.get('off')
            on_s   = self._fmt_time(on_t)
            off_s  = self._fmt_time(off_t)
            total  = self._fmt_duration(on_t, off_t)
            prefix = f"DG - {idx}" if idx == 1 else f"DG-{idx} " if idx == 2 else f"DG -{idx}"
            dg_lines.append(
                f"{prefix} is Switched ON  @  {on_s} & Switched OFF @ {off_s} Total Hrs {total}"
            )

        reason_text = outage.get('reason') or "to be updated"
        reason_line = (
            f"Reason : {reason_text}"
            f" ( External Power Cut  / Internal Trip / Fuse Blown )"
            f"  ( OR )  ( to be updated )"
        )

        event_dt = self._fmt_time(outage.get('eb_off_time') or time.time())
        subject = f"Power Cut Information - {event_dt}"

        body = (
            "Greetings!!\n\n"
            "Sub: Power Cut Information -Reg\n\n"
            f"EB Power Is Power  cut @  {eb_cut} & Resumed  @ {eb_resume} Total Hrs {eb_total}\n"
            + "\n".join(dg_lines)
            + f"\n\n\n{reason_line}\n\n"
            "Thank you"
        )

        try:
            success = self._send_smtp(subject, body)
            if success:
                self.last_notification_time = time.time()
            return success
        except Exception as e:
            logger.error(f"Error sending outage notification: {e}", exc_info=True)
            return False
