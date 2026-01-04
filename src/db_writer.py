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
        database: str = "ebpc"
    ):
        """Initialize database writer."""
        if not MYSQL_AVAILABLE:
            raise ImportError("MySQL connector not available")
        
        self.connection_params = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database,
            'autocommit': True
        }
        self.database = database
        
        # Ensure database exists
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """Ensure database exists, create if it doesn't."""
        conn = None
        try:
            # Connect without database first
            params = self.connection_params.copy()
            params.pop('database', None)
            conn = mysql.connector.connect(**params)
            cursor = conn.cursor()
            
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            conn.commit()
            cursor.close()
            
            logger.info(f"Database '{self.database}' ensured to exist")
        except Error as e:
            logger.error(f"Error ensuring database exists: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def _get_connection(self):
        """Get database connection."""
        try:
            return mysql.connector.connect(**self.connection_params)
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Cannot connect to database: {e}")
    
    def insert_event(
        self,
        input_id: str,
        input_name: str,
        state: int,
        timestamp: float,
        event_counter: int,
        previous_off_time: Optional[float] = None,
        previous_on_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Insert a state change event."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (
                    input_id, input_name, state, timestamp, event_counter,
                    previous_off_time, previous_on_time, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                input_id,
                input_name,
                state,
                timestamp,
                event_counter,
                previous_off_time,
                previous_on_time,
                json.dumps(metadata) if metadata else None
            ))
            event_id = cursor.lastrowid
            conn.commit()
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
        off_interval: Optional[float] = None
    ) -> None:
        """Insert computed interval data."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO intervals (event_id, input_id, on_duration, off_interval)
                VALUES (%s, %s, %s, %s)
            """, (event_id, input_id, on_duration, off_interval))
            conn.commit()
        except Error as e:
            logger.error(f"Error inserting interval: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()



