#!/usr/bin/env python3
import json
import sys
import getpass
import subprocess

CONFIG_FILE = "/opt/power-monitor/config.json"
DEFAULT_DB = "ebpc"

def print_header(text):
    print("=" * 70)
    print(f"{text:^70}")
    print("=" * 70)

def run_mysql_cmd(sql, host, user, password):
    cmd = ["mysql", f"-h{host}", f"-u{user}", f"-p{password}", "-e", sql]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr

def test_and_setup_mysql(host, port, user, password, database):
    try:
        import mysql.connector
        try:
            conn = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute(f"USE `{database}`;")
            conn.commit()
            cursor.close()
            conn.close()
            return True, None
        except mysql.connector.Error as e:
            return False, str(e)
    except ImportError:
        ok, err = run_mysql_cmd(
            f"CREATE DATABASE IF NOT EXISTS `{database}`;",
            host, user, password
        )
        if ok:
            return True, None
        return False, err

def auto_setup_fresh_mariadb(database):
    try:
        result = subprocess.run(
            ["mysql", "-u", "root", "--skip-password", "-e",
             f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["mysql", "-u", "root", "-e",
             f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    return False

def save_config(host, port, user, password, database):
    config = {}
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except Exception:
        pass
    config["database"] = {
        "type": "mysql",
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[OK] Configuration saved to {CONFIG_FILE}")

def main():
    print_header("MySQL Configuration Wizard")
    print()
    print("This wizard will help you configure MySQL for Power Monitor.")
    print()

    print("Checking for fresh MariaDB installation...")
    if auto_setup_fresh_mariadb(DEFAULT_DB):
        print(f"[OK] Database '{DEFAULT_DB}' is ready (no password required).")
        try:
            save_config("localhost", 3306, "root", "", DEFAULT_DB)
            return 0
        except Exception as e:
            print(f"[ERR] Could not save config: {e}")

    print()
    print("Root access requires a password. Please enter your MySQL credentials:")
    print("(Press Enter to accept the default shown in brackets)")
    print()

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"\nAttempt {attempt}/{max_attempts}:")

        host = input("MySQL Host [localhost]: ").strip() or "localhost"
        port = input("MySQL Port [3306]: ").strip() or "3306"
        user = input("MySQL User [root]: ").strip() or "root"
        password = getpass.getpass("MySQL Password: ")
        database = input(f"Database Name [{DEFAULT_DB}]: ").strip() or DEFAULT_DB

        print()
        print("Testing connection and setting up database...")

        ok, err = test_and_setup_mysql(host, port, user, password, database)
        if ok:
            print(f"[OK] Connected and database '{database}' is ready!")
            try:
                save_config(host, port, user, password, database)
                return 0
            except Exception as e:
                print(f"[ERR] Failed to save configuration: {e}")
                return 1
        else:
            print(f"[ERR] Connection failed: {err}")
            if attempt < max_attempts:
                print("Please check your credentials and try again.")

    print()
    print("[ERR] Could not connect after 3 attempts.")
    print()
    print("You can configure MySQL manually later by editing:")
    print(f"  {CONFIG_FILE}")
    print()
    print("Common fixes on Raspberry Pi:")
    print("  sudo mysql -u root")
    print(f"  CREATE DATABASE {DEFAULT_DB};")
    print("  ALTER USER \'root\'@\'localhost\' IDENTIFIED BY \'yourpassword\';")
    print("  FLUSH PRIVILEGES;")
    return 1

if __name__ == "__main__":
    sys.exit(main())
