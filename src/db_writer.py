"""Database writer module for inserting events into MySQL database."""
import logging
from typing import Dict, Any, Optional
import json

try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_AVAILABLE = True
except ImportError:
    try:
        import pymysql
        MYSQL_AVAILABLE = True

        class PyMySQLWrapper:
            def connect(self, **kwargs):
                return pymysql.connect(**kwargs)

            class Error(Exception):
                pass

        mysql = PyMySQLWrapper()
        mysql.connector = mysql
        Error = Exception
    except ImportError:
        MYSQL_AVAILABLE = False

logger = logging.getLogger(__name__)


class DatabaseWriter:
    """Database writer for inserting events."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "ebpc",
    ):
        if not MYSQL_AVAILABLE:
            raise ImportError("MySQL connector not available")

        self.connection_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "autocommit": True,
        }
        self.database = database
        self._event_counter = 0
        self._last_state: Dict[str, Dict[str, Optional[float]]] = {}
        self._ensure_database_and_tables()

    def _ensure_database_and_tables(self) -> None:
        conn = None
        try:
            params = self.connection_params.copy()
            params.pop("database", None)
            conn = mysql.connector.connect(**params)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            conn.commit()
            cursor.close()
            conn.close()

            conn = mysql.connector.connect(**self.connection_params)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    input_id VARCHAR(50) NOT NULL,
                    input_name VARCHAR(100) NOT NULL,
                    state INT NOT NULL,
                    timestamp DOUBLE NOT NULL,
                    event_counter INT NOT NULL,
                    previous_off_time DOUBLE,
                    previous_on_time DOUBLE,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_input_timestamp (input_id, timestamp),
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS intervals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_id INT NOT NULL,
                    input_id VARCHAR(50) NOT NULL,
                    on_duration DOUBLE,
                    off_interval DOUBLE,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS outages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    outage_start DOUBLE NOT NULL,
                    outage_end DOUBLE,
                    generator_input_id VARCHAR(50),
                    generator_start_time DOUBLE,
                    duration_seconds DOUBLE,
                    notification_sent INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_outage_start (outage_start)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            conn.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error ensuring database/tables: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _get_connection(self):
        try:
            return mysql.connector.connect(**self.connection_params)
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Cannot connect to database: {e}")

    def test_connection(self) -> bool:
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def record_event(
        self,
        input_id: str,
        input_name: str,
        state: int,
        timestamp: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        self._event_counter += 1
        last = self._last_state.get(input_id, {"off": None, "on": None})
        previous_off_time = last.get("off")
        previous_on_time = last.get("on")
        if state == 0:
            last["off"] = timestamp
        else:
            last["on"] = timestamp
        self._last_state[input_id] = last

        return self.insert_event(
            input_id=input_id,
            input_name=input_name,
            state=state,
            timestamp=timestamp,
            event_counter=self._event_counter,
            previous_off_time=previous_off_time,
            previous_on_time=previous_on_time,
            metadata=metadata,
        )

    def insert_event(
        self,
        input_id: str,
        input_name: str,
        state: int,
        timestamp: float,
        event_counter: int,
        previous_off_time: Optional[float] = None,
        previous_on_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (
                    input_id, input_name, state, timestamp, event_counter,
                    previous_off_time, previous_on_time, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    input_id,
                    input_name,
                    state,
                    timestamp,
                    event_counter,
                    previous_off_time,
                    previous_on_time,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            event_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return event_id
        except Error as e:
            logger.error(f"Error inserting event: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def insert_interval(
        self,
        event_id: int,
        input_id: str,
        on_duration: Optional[float] = None,
        off_interval: Optional[float] = None,
    ) -> None:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO intervals (event_id, input_id, on_duration, off_interval)
                VALUES (%s, %s, %s, %s)
                """,
                (event_id, input_id, on_duration, off_interval),
            )
            conn.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error inserting interval: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def insert_outage(self, outage_start: float) -> int:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO outages (outage_start)
                VALUES (%s)
                """,
                (outage_start,),
            )
            outage_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return outage_id
        except Error as e:
            logger.error(f"Error inserting outage: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def update_outage_end(self, outage_id: int, outage_end: float, duration_seconds: float) -> None:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE outages
                SET outage_end = %s, duration_seconds = %s
                WHERE id = %s
                """,
                (outage_end, duration_seconds, outage_id),
            )
            conn.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error updating outage end: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def update_outage_generator(
        self,
        outage_id: int,
        generator_input_id: str,
        generator_start_time: float,
        notification_sent: bool = False,
    ) -> None:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE outages
                SET generator_input_id = %s, generator_start_time = %s, notification_sent = %s
                WHERE id = %s
                """,
                (generator_input_id, generator_start_time, 1 if notification_sent else 0, outage_id),
            )
            conn.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error updating outage generator: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def close(self) -> None:
        return



