"""WhatsApp message sender with interval time notification."""
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning("python-dotenv not available. Environment variables must be set manually.")

logger = logging.getLogger(__name__)


class WhatsAppSender:
    """Sends WhatsApp notifications with interval time information."""
    
    def __init__(self):
        """Initialize WhatsApp sender from environment variables."""
        self.enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
        self.provider = os.getenv("WHATSAPP_PROVIDER", "twilio")
        self.rate_limit_seconds = int(os.getenv("WHATSAPP_RATE_LIMIT_SECONDS", "300"))
        self.last_notification_time: Optional[float] = None
        
        if self.enabled:
            self._init_provider()
        else:
            logger.info("WhatsApp notifications are disabled")
    
    def _init_provider(self) -> None:
        """Initialize the configured WhatsApp provider."""
        try:
            if self.provider == "twilio":
                self._init_twilio()
            elif self.provider == "cloud_api":
                self._init_cloud_api()
            else:
                logger.error(f"Unknown WhatsApp provider: {self.provider}")
                self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp provider: {e}")
            self.enabled = False
    
    def _init_twilio(self) -> None:
        """Initialize Twilio provider."""
        try:
            from twilio.rest import Client
            
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env file")
            
            self.twilio_client = Client(account_sid, auth_token)
            self.from_number = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
            self.to_number = os.getenv("TWILIO_TO_NUMBER")
            
            if not self.to_number:
                raise ValueError("TWILIO_TO_NUMBER must be set in .env file")
            
            logger.info("Twilio WhatsApp provider initialized")
        except ImportError:
            logger.error("twilio package not installed. Install with: pip install twilio")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {e}")
            self.enabled = False
    
    def _init_cloud_api(self) -> None:
        """Initialize WhatsApp Cloud API provider."""
        try:
            import requests
            self.requests = requests
            
            access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
            phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
            self.to_number = os.getenv("WHATSAPP_TO_NUMBER")
            
            if not access_token or not phone_number_id or not self.to_number:
                raise ValueError("WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, and WHATSAPP_TO_NUMBER must be set in .env file")
            
            self.access_token = access_token
            self.phone_number_id = phone_number_id
            self.api_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            
            logger.info("WhatsApp Cloud API provider initialized")
        except ImportError:
            logger.error("requests package not installed. Install with: pip install requests")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp Cloud API: {e}")
            self.enabled = False
    
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
        """Format WhatsApp message with interval time."""
        outage_start_dt = datetime.fromtimestamp(outage_start_time)
        generator_start_dt = datetime.fromtimestamp(generator_start_time)
        
        interval_str = self._format_duration(interval_seconds)
        
        message = f"""🚨 Power Event Alert

⚡ Generator Activated: {generator_name}

📅 Power Cut Started:
   {outage_start_dt.strftime("%Y-%m-%d %H:%M:%S")}

🔄 Generator Started:
   {generator_start_dt.strftime("%Y-%m-%d %H:%M:%S")}

⏱️ INTERVAL TIME (Power Cut → Generator ON):
   {interval_str}
   ({interval_seconds:.0f} seconds)

Status: Generator is now active"""
        
        return message
    
    def _check_rate_limit(self) -> bool:
        """Check if enough time has passed since last notification."""
        if self.last_notification_time is None:
            return True
        
        elapsed = time.time() - self.last_notification_time
        if elapsed < self.rate_limit_seconds:
            remaining = self.rate_limit_seconds - elapsed
            logger.info(f"Rate limit active. Next notification allowed in {remaining:.0f} seconds")
            return False
        
        return True
    
    def _send_twilio(self, message: str) -> bool:
        """Send message via Twilio."""
        try:
            message_obj = self.twilio_client.messages.create(
                from_=self.from_number,
                to=self.to_number,
                body=message
            )
            logger.info(f"WhatsApp message sent via Twilio. SID: {message_obj.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message via Twilio: {e}")
            return False
    
    def _send_cloud_api(self, message: str) -> bool:
        """Send message via WhatsApp Cloud API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": self.to_number,
                "type": "text",
                "text": {"body": message}
            }
            response = self.requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"WhatsApp message sent via Cloud API. Response: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message via Cloud API: {e}")
            return False
    
    def send_generator_activation_notification(
        self,
        generator_name: str,
        outage_start_time: float,
        generator_start_time: float
    ) -> bool:
        """
        Send WhatsApp notification when generator activates after power cut.
        
        Args:
            generator_name: Display name of the generator (e.g., "GEN1")
            outage_start_time: Timestamp when power cut started
            generator_start_time: Timestamp when generator started
            
        Returns:
            True if message was sent (or rate-limited), False on error
        """
        if not self.enabled:
            logger.debug("WhatsApp notifications are disabled")
            return False
        
        if not self._check_rate_limit():
            return False  # Rate limited
        
        # Calculate interval
        interval_seconds = generator_start_time - outage_start_time
        
        # Format message
        message = self._format_message(
            generator_name=generator_name,
            outage_start_time=outage_start_time,
            generator_start_time=generator_start_time,
            interval_seconds=interval_seconds
        )
        
        # Send message
        try:
            if self.provider == "twilio":
                success = self._send_twilio(message)
            elif self.provider == "cloud_api":
                success = self._send_cloud_api(message)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return False
            
            if success:
                self.last_notification_time = time.time()
            
            return success
        except Exception as e:
            logger.error(f"Error sending WhatsApp notification: {e}", exc_info=True)
            return False

