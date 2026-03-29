"""Email notification sender for power outage events."""
import html
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Optional, Dict, Any

from .config import Config  # type: ignore

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not available. Environment variables must be set manually.")

logger = logging.getLogger(__name__)

_OUTAGE_HTML_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "outage_email.html"


class EmailSender:
    """Sends power outage summary email notifications."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config
        self.last_notification_time: Optional[float] = None
        self._load_settings()

    def _load_settings(self) -> None:
        """Load (or reload) settings from config.json."""
        if not self.config:
            logger.error("No config provided to EmailSender")
            self.enabled = False
            return

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

    def _send_smtp(
        self,
        subject: str,
        body_plain: str,
        body_html: Optional[str] = None,
    ) -> bool:
        try:
            if body_html:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body_plain, "plain", "utf-8"))
                msg.attach(MIMEText(body_html, "html", "utf-8"))
            else:
                msg = MIMEMultipart()
                msg.attach(MIMEText(body_plain, "plain", "utf-8"))
            msg['From'] = self.email_from
            msg['To'] = ", ".join(self.emails_to)
            msg['Subject'] = subject

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
    def _fmt_duration_dhm(t_start: Optional[float], t_end: Optional[float]) -> str:
        if t_start is None:
            return "---"
        if t_end is None:
            return "Ongoing"
        secs = int(max(t_end - t_start, 0))
        days, rem = divmod(secs, 86400)
        hours, rem2 = divmod(rem, 3600)
        minutes = rem2 // 60
        parts = []
        if days:
            parts.append(f"{days}d")
        parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)

    def _render_outage_html(self, outage: Dict[str, Any], reason_text: str) -> Optional[str]:
        if not _OUTAGE_HTML_TEMPLATE.is_file():
            logger.warning("Outage HTML template missing at %s", _OUTAGE_HTML_TEMPLATE)
            return None
        try:
            raw = _OUTAGE_HTML_TEMPLATE.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Could not read outage HTML template: %s", e)
            return None

        eb_off_t = outage.get("eb_off_time")
        eb_on_t = outage.get("eb_on_time")
        subs = {
            "eb_powercut": html.escape(self._fmt_time(eb_off_t)),
            "eb_resumed": html.escape(self._fmt_time(eb_on_t)),
            "eb_total_dhm": html.escape(self._fmt_duration_dhm(eb_off_t, eb_on_t)),
            "reason": html.escape(reason_text),
        }
        for idx, key in enumerate(["gen1", "gen2", "gen3"], start=1):
            g = outage.get(key, {})
            on_t = g.get("on")
            off_t = g.get("off")
            subs[f"dg{idx}_on"] = html.escape(self._fmt_time(on_t))
            subs[f"dg{idx}_off"] = html.escape(self._fmt_time(off_t))
            subs[f"dg{idx}_runtime"] = html.escape(self._fmt_duration_dhm(on_t, off_t))
        try:
            return Template(raw).substitute(**subs)
        except (KeyError, ValueError) as e:
            logger.error("Outage HTML template substitute failed: %s", e)
            return None

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

        eb_off_t = outage.get("eb_off_time")
        eb_on_t = outage.get("eb_on_time")
        eb_off = self._fmt_time(eb_off_t)
        eb_on = self._fmt_time(eb_on_t)
        eb_total_dhm = self._fmt_duration_dhm(eb_off_t, eb_on_t)

        timing_lines = [
            f"EB (main supply)",
            f"  Power cut: {eb_off}   Resumed: {eb_on}   Total duration: {eb_total_dhm}",
            "",
            "DG (generators)",
        ]
        for idx, key in enumerate(["gen1", "gen2", "gen3"], start=1):
            g = outage.get(key, {})
            on_t = g.get("on")
            off_t = g.get("off")
            on_s = self._fmt_time(on_t)
            off_s = self._fmt_time(off_t)
            runtime = self._fmt_duration_dhm(on_t, off_t)
            timing_lines.append(
                f"  DG-{idx}  Switch ON: {on_s}   Switch OFF: {off_s}   Run time: {runtime}"
            )

        reason_text = outage.get("reason") or "to be updated"
        reason_line = f"Reason: {reason_text}"

        event_dt = self._fmt_time(outage.get("eb_off_time") or time.time())
        subject = f"Power Cut Information - {event_dt}"

        body_plain = (
            "Greetings,\n\n"
            "Subject: Power Cut Information\n\n"
            + "\n".join(timing_lines)
            + f"\n\n{reason_line}\n\n"
            "Thank you."
        )

        body_html = self._render_outage_html(outage, reason_text)

        try:
            success = self._send_smtp(subject, body_plain, body_html)
            if success:
                self.last_notification_time = time.time()
            return success
        except Exception as e:
            logger.error(f"Error sending outage notification: {e}", exc_info=True)
            return False

    def send_test_email(self) -> bool:
        """Send a test email to verify SMTP settings and recipients."""
        self._load_settings()

        if not self.smtp_username or not self.smtp_password:
            logger.warning("Test email: missing SMTP username or password")
            return False
        if not self.emails_to:
            logger.warning("Test email: no recipients configured")
            return False

        subject = "Power Monitor — Test Email"
        body = (
            "This is a test message from the Power Monitor application.\n\n"
            f"Recipients: {', '.join(self.emails_to)}\n"
            f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "If you received this, outage alerts will be delivered to these addresses "
            "when email notifications are enabled and the background service detects power events."
        )
        return self._send_smtp(subject, body)

