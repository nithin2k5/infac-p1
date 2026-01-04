#!/usr/bin/env python3
"""MySQL Configuration Wizard for Power Monitor"""
import json
import sys
import getpass
import subprocess

def print_header(text):
    print("=" * 70)
    print(f"{text:^70}")
    print("=" * 70)

def test_mysql_connection(host, port, user, password, database):
    """Test MySQL connection."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def main():
    print_header("MySQL Configuration Wizard")
    print()
    print("This wizard will help you configure MySQL for Power Monitor.")
    print()
    
    # Get MySQL credentials
    print("Please enter your MySQL credentials:")
    print()
    
    host = input("MySQL Host [localhost]: ").strip() or "localhost"
    port = input("MySQL Port [3306]: ").strip() or "3306"
    user = input("MySQL User [root]: ").strip() or "root"
    password = getpass.getpass("MySQL Password: ")
    database = input("Database Name [ebpc]: ").strip() or "ebpc"
    
    print()
    print("Testing connection...")
    
    # Test connection
    if test_mysql_connection(host, int(port), user, password, database):
        print("✓ Connection successful!")
        
        # Update config.json
        config_file = "/opt/power-monitor/config.json"
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            config['database'] = {
                "type": "mysql",
                "host": host,
                "port": int(port),
                "user": user,
                "password": password,
                "database": database
            }
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✓ Configuration saved to {config_file}")
            return 0
        except Exception as e:
            print(f"✗ Failed to save configuration: {e}")
            return 1
    else:
        print("✗ Connection failed. Please check your credentials.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
