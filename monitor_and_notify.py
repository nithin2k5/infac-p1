#!/usr/bin/env python3
"""Monitor database for generator activations and send WhatsApp notifications."""
import sys
import os
import time
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.db_reader import DatabaseReader
from src.db_writer import DatabaseWriter
from src.whatsapp_sender import WhatsAppSender

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class GeneratorMonitor:
    """Monitors database for generator activations after power cuts."""
    
    def __init__(self):
        """Initialize the monitor."""
        # Load configuration
        config = Config("config.json")
        db_config = config.get_database_config()
        
        # Initialize database reader
        self.db_reader = DatabaseReader(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", "12345678"),
            database=db_config.get("database", "ebpc")
        )
        
        # Initialize database writer (for updating outage records)
        self.db_writer = DatabaseWriter(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", "12345678"),
            database=db_config.get("database", "ebpc")
        )
        
        # Initialize WhatsApp sender
        self.whatsapp = WhatsAppSender()
        
        # Track notified outages
        self.notified_outages = set()
    
    def check_and_notify(self) -> int:
        """
        Check for generator activations and send notifications.
        
        Returns:
            Number of notifications sent
        """
        notifications_sent = 0
        
        try:
            # Get active outage
            active_outage = self.db_reader.get_active_outage()
            
            if not active_outage:
                return 0
            
            outage_id = active_outage['id']
            outage_start = active_outage['outage_start']
            
            # Skip if already notified
            if outage_id in self.notified_outages:
                return 0
            
            # Get latest states
            latest_states = self.db_reader.get_latest_states()
            
            # Check generators
            generators = [
                ('gen1', 'GEN1', 'Generator 1'),
                ('gen2', 'GEN2', 'Generator 2'),
                ('gen3', 'GEN3', 'Generator 3'),
            ]
            
            for gen_id, gen_short, gen_name in generators:
                if gen_id not in latest_states:
                    continue
                
                gen_state = latest_states[gen_id]
                
                # Check if generator is ON and started after outage
                if gen_state['state'] == 1:
                    gen_start_time = gen_state['timestamp']
                    
                    # Generator must have started after outage
                    if gen_start_time >= outage_start:
                        # Calculate interval
                        interval = gen_start_time - outage_start
                        
                        logger.info(
                            f"Generator {gen_name} activated after {interval:.0f}s outage. "
                            f"Sending WhatsApp notification..."
                        )
                        
                        # Send WhatsApp notification
                        success = self.whatsapp.send_generator_activation_notification(
                            generator_name=gen_name,
                            outage_start_time=outage_start,
                            generator_start_time=gen_start_time
                        )
                        
                        if success:
                            notifications_sent += 1
                            # Mark outage as notified
                            self.notified_outages.add(outage_id)
                            
                            logger.info(f"WhatsApp notification sent for {gen_name}")
                            
                            # Record outage end in database
                            self._record_outage_end(
                                outage_id=outage_id,
                                generator_input_id=gen_id,
                                generator_start_time=gen_start_time,
                                duration_seconds=interval
                            )
                        
                        break  # Only notify for first generator that activates
            
            return notifications_sent
            
        except Exception as e:
            logger.error(f"Error checking and notifying: {e}", exc_info=True)
            return 0
    
    def _record_outage_end(
        self,
        outage_id: int,
        generator_input_id: str,
        generator_start_time: float,
        duration_seconds: float
    ) -> None:
        """Record outage end in database."""
        try:
            conn = self.db_writer._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE outages 
                SET outage_end = %s,
                    generator_input_id = %s,
                    generator_start_time = %s,
                    duration_seconds = %s,
                    notification_sent = 1
                WHERE id = %s
            """, (generator_start_time, generator_input_id, generator_start_time, duration_seconds, outage_id))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error recording outage end: {e}")


def main():
    """Main function to run the monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor for generator activations and send WhatsApp')
    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='Check interval in seconds (default: 10)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Check once and exit'
    )
    args = parser.parse_args()
    
    print("="*60)
    print("Generator Activation Monitor & WhatsApp Notifier")
    print("="*60)
    
    try:
        monitor = GeneratorMonitor()
        
        if not monitor.whatsapp.enabled:
            print("\n⚠ WhatsApp notifications are disabled.")
            print("  Set WHATSAPP_ENABLED=true in .env file to enable.")
            return
        
        print(f"✓ WhatsApp provider: {monitor.whatsapp.provider}")
        print(f"✓ Monitoring database: ebpc")
        print(f"✓ Check interval: {args.interval} seconds")
        
        if args.once:
            print("\nChecking once...")
            notifications = monitor.check_and_notify()
            if notifications > 0:
                print(f"✓ Sent {notifications} notification(s)")
            else:
                print("✓ No new generator activations requiring notifications")
        else:
            print("\nStarting continuous monitoring...")
            print("Press Ctrl+C to stop\n")
            
            try:
                while True:
                    notifications = monitor.check_and_notify()
                    if notifications > 0:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent {notifications} notification(s)")
                    
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n\nStopping monitor...")
                print("✓ Monitor stopped")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

