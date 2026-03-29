"""Email notification sender with interval time notification."""
import os
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List
from .config import Config  # type: ignore
# Try to load .env file
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning("python-dotenv not available. Environment variables must be set manually.")

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends Email notifications with interval time information."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Email sender from config or environment variables.
        
        Args:
            config: Config object to load settings from.
        """
        self.config = config
        
        if config:
            self.enabled = config.get("email.enabled", False)
            self.rate_limit_seconds = int(config.get("email.rate_limit_seconds", 300))
            
            self.smtp_server = config.get("email.smtp_server", "smtp.gmail.com")
            self.smtp_port = int(config.get("email.smtp_port", 587))
            self.smtp_username = config.get("email.smtp_username", "")
            self.smtp_password = config.get("email.smtp_password", "")
            self.email_from = config.get("email.from", self.smtp_username or "")
            
            # Handle multiple emails (comma separated or list)
            to_val = config.get("email.to", "")
            if isinstance(to_val, list):
                self.emails_to = to_val
            else:
                self.emails_to = [e.strip() for e in str(to_val).split(",") if e.strip()]
        else:
            # Fallback to environment variables
            self.enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
            self.rate_limit_seconds = int(os.getenv("EMAIL_RATE_LIMIT_SECONDS", "300"))
            
            self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
            self.smtp_username = os.getenv("SMTP_USERNAME", "")
            self.smtp_password = os.getenv("SMTP_PASSWORD", "")
            self.email_from = os.getenv("EMAIL_FROM", self.smtp_username or "")
            
            to_env = os.getenv("EMAIL_TO", "")
            self.emails_to = [e.strip() for e in to_env.split(",") if e.strip()]
        
        self.last_notification_time: Optional[float] = None
        
        if not self.enabled:
            logger.info("Email notifications are disabled")
        elif not all([self.smtp_username, self.smtp_password, self.emails_to]):
            logger.warning("Email is enabled but missing SMTP credentials or destination")
            self.enabled = False
        else:
            logger.info(f"Email notification provider initialized with {len(self.emails_to)} recipients")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes} minutes {secs} seconds"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours} hours {minutes} minutes {secs} seconds"
    
    def _format_message(
        self,
        generator_name: str,
        outage_start_time: float,
        generator_start_time: float,
        interval_seconds: float
    ) -> str:
        """Format email message body with interval time."""
        outage_start_dt = datetime.fromtimestamp(outage_start_time)
        generator_start_dt = datetime.fromtimestamp(generator_start_time)
        
        interval_str = self._format_duration(interval_seconds)
        
        message = f"""POWER EVENT ALERT

Generator Activated: {generator_name}

Power Cut Started:
{outage_start_dt.strftime("%Y-%m-%d %H:%M:%S")}

Generator Started:
{generator_start_dt.strftime("%Y-%m-%d %H:%M:%S")}

INTERVAL TIME (Power Cut to Generator ON):
{interval_str} ({interval_seconds:.0f} seconds)

Status: Generator is now active.
"""
        return message
    
    def _check_rate_limit(self) -> bool:
        """Check if enough time has passed since last notification."""
        if self.last_notification_time is None:
            return True
        
        last_t = self.last_notification_time
        last_time = last_t if last_t is not None else 0.0
        elapsed = time.time() - last_time
        if elapsed < self.rate_limit_seconds:
            remaining = self.rate_limit_seconds - elapsed
            logger.info(f"Rate limit active. Next notification allowed in {remaining:.0f} seconds")
            return False
        
        return True
    
    def _reload_config(self) -> None:
        """Re-read settings from config file so runtime changes (e.g. new recipients) are picked up."""
        if not self.config:
            return
        try:
            self.config.load()
        except Exception as e:
            logger.warning(f"Could not reload config before sending email: {e}")
            return

        self.enabled = self.config.get("email.enabled", False)
        self.rate_limit_seconds = int(self.config.get("email.rate_limit_seconds", 300))
        self.smtp_server = self.config.get("email.smtp_server", "smtp.gmail.com")
        self.smtp_port = int(self.config.get("email.smtp_port", 587))
        self.smtp_username = self.config.get("email.smtp_username", "")
        self.smtp_password = self.config.get("email.smtp_password", "")
        self.email_from = self.config.get("email.from", self.smtp_username or "")

        to_val = self.config.get("email.to", "")
        if isinstance(to_val, list):
            self.emails_to = to_val
        else:
            self.emails_to = [e.strip() for e in str(to_val).split(",") if e.strip()]

    def _send_email(self, subject: str, message_body: str) -> bool:
        """Send message via SMTP."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from or ""
            msg['To'] = ", ".join(self.emails_to)
            msg['Subject'] = subject

            msg.attach(MIMEText(message_body, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username or "", self.smtp_password or "")
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent to: {', '.join(self.emails_to)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Email message: {e}")
            return False
    
    def send_generator_activation_notification(
        self,
        generator_name: str,
        outage_start_time: float,
        generator_start_time: float
    ) -> bool:
        """
        Send Email notification when generator activates after power cut.
        
        Args:
            generator_name: Display name of the generator (e.g., "GEN1")
            outage_start_time: Timestamp when power cut started
            generator_start_time: Timestamp when generator started
            
        Returns:
            True if message was sent (or rate-limited), False on error
        """
        # Reload settings so recipients/credentials added via GUI are used
        self._reload_config()

        if not self.enabled:
            logger.debug("Email notifications are disabled")
            return False

        if not all([self.smtp_username, self.smtp_password, self.emails_to]):
            logger.warning("Email enabled but missing credentials or recipients — not sending")
            return False

        if not self._check_rate_limit():
            return False
        
        # Calculate interval
        interval_seconds = generator_start_time - outage_start_time
        
        # Format message
        message = self._format_message(
            generator_name=generator_name,
            outage_start_time=outage_start_time,
            generator_start_time=generator_start_time,
            interval_seconds=interval_seconds
        )
        
        subject = f"Alert: {generator_name} Activated"
        
        try:
            success = self._send_email(subject, message)
            if success:
                self.last_notification_time = time.time()
            return success
        except Exception as e:
            logger.error(f"Error sending Email notification: {e}", exc_info=True)
            return False

    def send_test_email(self) -> bool:
        """Send a test email to verify SMTP settings and recipients."""
        self._reload_config()

        if not all([self.smtp_username, self.smtp_password, self.emails_to]):
            logger.warning("Test email: missing credentials or recipients")
            return False

        subject = "Power Monitor — Test Email"
        body = (
            "This is a test email from your Power Monitor application.\n\n"
            "If you received this, your email notification settings are working correctly.\n\n"
            f"Recipients: {', '.join(self.emails_to)}\n"
            f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self._send_email(subject, body)
