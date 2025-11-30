#!/usr/bin/env python3
"""Check for generator activations and send WhatsApp notifications."""
import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.db_reader import DatabaseReader
from src.whatsapp_sender import WhatsAppSender

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def check_and_send_notifications():
    """Check for generator activations and send WhatsApp notifications."""
    print("="*60)
    print("Checking for Generator Activations and Sending WhatsApp Messages")
    print("="*60)
    
    # Load configuration
    config = Config("config.json")
    db_config = config.get_database_config()
    
    try:
        # Initialize database reader
        db = DatabaseReader(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", "12345678"),
            database=db_config.get("database", "ebpc")
        )
        
        print(f"\n✓ Connected to database: {db_config.get('database')}")
        
        # Initialize WhatsApp sender
        whatsapp = WhatsAppSender()
        
        if not whatsapp.enabled:
            print("\n⚠ WhatsApp notifications are disabled.")
            print("  Set WHATSAPP_ENABLED=true in .env file to enable.")
            return True
        
        print(f"✓ WhatsApp provider: {whatsapp.provider}")
        
        # Get active outage
        active_outage = db.get_active_outage()
        
        if not active_outage:
            print("\n✓ No active power outage detected.")
            print("  No notifications needed.")
            return True
        
        print(f"\n⚠ Active power outage detected!")
        outage_start = active_outage['outage_start']
        outage_start_dt = datetime.fromtimestamp(outage_start)
        print(f"  Outage started at: {outage_start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check for generators that started after outage
        # Get latest states
        latest_states = db.get_latest_states()
        
        # Check each generator
        generators = [
            ('gen1', 'GEN1', 'Generator 1'),
            ('gen2', 'GEN2', 'Generator 2'),
            ('gen3', 'GEN3', 'Generator 3'),
        ]
        
        notifications_sent = 0
        
        for gen_id, gen_short, gen_name in generators:
            if gen_id not in latest_states:
                continue
            
            gen_state = latest_states[gen_id]
            
            # Check if generator is ON
            if gen_state['state'] == 1:
                gen_start_time = gen_state['timestamp']
                
                # Check if generator started after outage
                if gen_start_time >= outage_start:
                    # Check if notification already sent (check metadata or outages table)
                    # For simplicity, we'll check if outage_end is not set
                    if not active_outage.get('outage_end'):
                        print(f"\n📱 Generator {gen_name} is ON after power cut!")
                        print(f"  Generator started at: {datetime.fromtimestamp(gen_start_time).strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # Calculate interval
                        interval = gen_start_time - outage_start
                        interval_str = whatsapp._format_duration(interval)
                        print(f"  Interval: {interval_str}")
                        
                        # Send WhatsApp notification
                        success = whatsapp.send_generator_activation_notification(
                            generator_name=gen_name,
                            outage_start_time=outage_start,
                            generator_start_time=gen_start_time
                        )
                        
                        if success:
                            print(f"  ✓ WhatsApp notification sent successfully!")
                            notifications_sent += 1
                        else:
                            print(f"  ✗ Failed to send WhatsApp notification")
                    else:
                        print(f"\n  Generator {gen_name} is ON, but notification already sent.")
        
        if notifications_sent == 0:
            print("\n✓ No new generator activations requiring notifications.")
        else:
            print(f"\n✓ Sent {notifications_sent} notification(s).")
        
        return True
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        return False


def simulate_generator_activation():
    """Simulate a generator activation for testing."""
    print("="*60)
    print("Testing WhatsApp Notification - Simulating Generator Activation")
    print("="*60)
    
    # Initialize WhatsApp sender
    whatsapp = WhatsAppSender()
    
    if not whatsapp.enabled:
        print("\n⚠ WhatsApp notifications are disabled.")
        print("  Set WHATSAPP_ENABLED=true in .env file to enable.")
        return False
    
    # Simulate times
    import time
    now = time.time()
    outage_start = now - 300  # 5 minutes ago
    generator_start = now  # Now
    
    print(f"\nSimulating:")
    print(f"  Outage started: {datetime.fromtimestamp(outage_start).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Generator started: {datetime.fromtimestamp(generator_start).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Interval: {whatsapp._format_duration(300)}")
    
    # Send test notification
    print(f"\nSending test WhatsApp message...")
    success = whatsapp.send_generator_activation_notification(
        generator_name="GEN1",
        outage_start_time=outage_start,
        generator_start_time=generator_start
    )
    
    if success:
        print("✓ Test notification sent successfully!")
    else:
        print("✗ Failed to send test notification")
    
    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Check and send WhatsApp notifications')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Send a test notification instead of checking database'
    )
    args = parser.parse_args()
    
    if args.test:
        success = simulate_generator_activation()
    else:
        success = check_and_send_notifications()
    
    sys.exit(0 if success else 1)

