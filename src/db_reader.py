"""Database reader module for read-only access to MySQL database."""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_AVAILABLE = True
    USE_PYMYSQL = False
except ImportError:
    try:
        import pymysql
        MYSQL_AVAILABLE = True
        USE_PYMYSQL = True
        # Compatibility wrapper
        class PyMySQLWrapper:
            def connect(self, **kwargs):
                return pymysql.connect(**kwargs)
            class Error(Exception):
                pass
        mysql = PyMySQLWrapper()
        mysql.connector = mysql
    except ImportError:
        MYSQL_AVAILABLE = False
        USE_PYMYSQL = False

logger = logging.getLogger(__name__)


class DatabaseReader:
    """Read-only database access for monitoring events."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "rpi_monitor"
    ):
        """
        Initialize database reader.
        
        Args:
            host: MySQL host
            port: MySQL port
            user: MySQL username
            password: MySQL password
            database: Database name
        """
        if not MYSQL_AVAILABLE:
            raise ImportError(
                "MySQL connector not available. Install with: "
                "pip install mysql-connector-python or pip install pymysql"
            )
        
        self.connection_params = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database,
            'autocommit': True
        }
        self.database = database
        
        # Ensure database and tables exist
        self._ensure_database_and_tables()
    
    def _ensure_database_and_tables(self) -> None:
        """Ensure database and tables exist."""
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
            conn.close()
            
            logger.info(f"Database '{self.database}' ensured to exist")
            
            # Now connect to the database and create tables
            conn = mysql.connector.connect(**self.connection_params)
            cursor = conn.cursor()
            
            # Events table
            cursor.execute("""
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
            """)
            
            # Intervals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intervals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_id INT NOT NULL,
                    input_id VARCHAR(50) NOT NULL,
                    on_duration DOUBLE,
                    off_interval DOUBLE,
                    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Outages table
            cursor.execute("""
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
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Tables ensured to exist in '{self.database}'")
            
        except Error as e:
            logger.error(f"Error ensuring database/tables: {e}")
            raise
    
    def _get_connection(self):
        """Get database connection."""
        try:
            return mysql.connector.connect(**self.connection_params)
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Cannot connect to database: {e}")
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_events(
        self,
        input_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        event_type: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "timestamp",
        order_desc: bool = True
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Query events with filters and pagination.
        
        Returns:
            Tuple of (events list, total count)
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Build WHERE clause
            conditions = []
            params = []
            
            if input_id:
                conditions.append("e.input_id = %s")
                params.append(input_id)
            
            if start_time:
                conditions.append("e.timestamp >= %s")
                params.append(start_time)
            
            if end_time:
                conditions.append("e.timestamp <= %s")
                params.append(end_time)
            
            if event_type:
                if event_type == "ON":
                    conditions.append("e.state = 1")
                elif event_type == "OFF":
                    conditions.append("e.state = 0")
            
            if search_text:
                conditions.append("(e.input_name LIKE %s OR e.metadata LIKE %s)")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern])
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM events e {where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']
            
            # Build ORDER BY
            order_clause = f"ORDER BY e.{order_by}"
            if order_desc:
                order_clause += " DESC"
            else:
                order_clause += " ASC"
            
            # Build LIMIT/OFFSET
            limit_clause = ""
            if limit:
                limit_clause = f"LIMIT {limit} OFFSET {offset}"
            
            # Main query
            query = f"""
                SELECT 
                    e.id, e.input_id, e.input_name, e.state, e.timestamp,
                    e.event_counter, e.previous_off_time, e.previous_on_time,
                    e.metadata, i.on_duration, i.off_interval
                FROM events e
                LEFT JOIN intervals i ON e.id = i.event_id
                {where_clause}
                {order_clause}
                {limit_clause}
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            events = []
            for row in rows:
                event = dict(row)
                # Parse metadata JSON
                if event.get('metadata'):
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except:
                        pass
                events.append(event)
            
            return events, total_count
            
        except Error as e:
            logger.error(f"Error querying events: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """Get a single event by ID."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    e.*, i.on_duration, i.off_interval
                FROM events e
                LEFT JOIN intervals i ON e.id = i.event_id
                WHERE e.id = %s
            """, (event_id,))
            
            row = cursor.fetchone()
            if row:
                event = dict(row)
                if event.get('metadata'):
                    try:
                        event['metadata'] = json.loads(event['metadata'])
                    except:
                        pass
                return event
            return None
            
        except Error as e:
            logger.error(f"Error getting event: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_statistics(
        self,
        input_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Get statistics for events."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            conditions = []
            params = []
            
            if input_id:
                conditions.append("input_id = %s")
                params.append(input_id)
            
            if start_time:
                conditions.append("timestamp >= %s")
                params.append(start_time)
            
            if end_time:
                conditions.append("timestamp <= %s")
                params.append(end_time)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            # Basic stats
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT input_id) as unique_inputs,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event
                FROM events
                {where_clause}
            """, params)
            
            stats = dict(cursor.fetchone())
            
            # Counts per input
            cursor.execute(f"""
                SELECT input_id, input_name, COUNT(*) as count
                FROM events
                {where_clause}
                GROUP BY input_id, input_name
            """, params)
            
            stats['counts_per_input'] = {row['input_id']: {
                'name': row['input_name'],
                'count': row['count']
            } for row in cursor.fetchall()}
            
            # Counts by state
            cursor.execute(f"""
                SELECT state, COUNT(*) as count
                FROM events
                {where_clause}
                GROUP BY state
            """, params)
            
            state_rows = cursor.fetchall()
            stats['counts_by_state'] = {
                'ON': sum(row['count'] for row in state_rows if row['state'] == 1),
                'OFF': sum(row['count'] for row in state_rows if row['state'] == 0)
            }
            
            # Outage stats
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_outages,
                    AVG(duration_seconds) as avg_duration,
                    SUM(duration_seconds) as total_duration
                FROM outages
                WHERE duration_seconds IS NOT NULL
            """)
            
            outage_row = cursor.fetchone()
            stats['outages'] = {
                'total': outage_row['total_outages'] or 0,
                'avg_duration': outage_row['avg_duration'] or 0,
                'total_duration': outage_row['total_duration'] or 0
            }
            
            return stats
            
        except Error as e:
            logger.error(f"Error getting statistics: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_latest_states(self) -> Dict[str, Dict[str, Any]]:
        """Get latest state for each input."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT e1.input_id, e1.input_name, e1.state, e1.timestamp, e1.event_counter
                FROM events e1
                WHERE e1.timestamp = (
                    SELECT MAX(e2.timestamp)
                    FROM events e2
                    WHERE e2.input_id = e1.input_id
                )
            """)
            
            states = {}
            for row in cursor.fetchall():
                states[row['input_id']] = {
                    'name': row['input_name'],
                    'state': row['state'],
                    'timestamp': row['timestamp'],
                    'counter': row['event_counter']
                }
            
            return states
            
        except Error as e:
            logger.error(f"Error getting latest states: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_active_outage(self) -> Optional[Dict[str, Any]]:
        """Get currently active outage if any."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM outages
                WHERE outage_end IS NULL
                ORDER BY outage_start DESC
                LIMIT 1
            """)
            
            return cursor.fetchone()
            
        except Error as e:
            logger.error(f"Error getting active outage: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_eb_power_history(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get EB power cut history - pairs OFF events with ON events.
        
        Returns:
            Tuple of (power history list, total count)
            Each item contains: off_time, on_time, duration_seconds, status
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Get all EB events oldest-first so OFF always precedes its matching ON
            cursor.execute("""
                SELECT id, state, timestamp
                FROM events
                WHERE input_id = 'eb'
                ORDER BY timestamp ASC
            """)

            all_events = cursor.fetchall()

            # Pair each OFF event with the next ON event
            power_history = []
            current_off = None

            for event in all_events:
                if event['state'] == 0:  # OFF event
                    if current_off:
                        power_history.append({
                            'off_time': current_off['timestamp'],
                            'on_time': None,
                            'duration_seconds': None,
                            'status': 'Ongoing'
                        })
                    current_off = event
                elif event['state'] == 1:  # ON event
                    if current_off:
                        duration = event['timestamp'] - current_off['timestamp']
                        power_history.append({
                            'off_time': current_off['timestamp'],
                            'on_time': event['timestamp'],
                            'duration_seconds': max(duration, 0),
                            'status': 'Completed'
                        })
                        current_off = None

            if current_off:
                power_history.append({
                    'off_time': current_off['timestamp'],
                    'on_time': None,
                    'duration_seconds': None,
                    'status': 'Ongoing'
                })

            # Show newest outages first
            power_history.reverse()
            
            total_count = len(power_history)
            
            # Apply pagination
            if limit:
                power_history = power_history[offset:offset + limit]
            else:
                power_history = power_history[offset:]
            
            return power_history, total_count
            
        except Error as e:
            logger.error(f"Error getting EB power history: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_daily_summary(self, since_hour: int = 6) -> Dict[str, Dict]:
        """
        Return today's ON/OFF durations and power-cut count for each input
        since `since_hour` (default 6 AM) up to now.
        """
        import time as _time
        from datetime import datetime as _dt, date as _date

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)

            today = _date.today()
            start_ts = _dt(today.year, today.month, today.day, since_hour).timestamp()
            now_ts = _time.time()

            inputs = ['eb', 'gen1', 'gen2', 'gen3']
            result = {}

            for input_id in inputs:
                cursor.execute("""
                    SELECT state FROM events
                    WHERE input_id = %s AND timestamp < %s
                    ORDER BY timestamp DESC LIMIT 1
                """, (input_id, start_ts))
                row = cursor.fetchone()
                initial_state = row['state'] if row else 1

                cursor.execute("""
                    SELECT state, timestamp FROM events
                    WHERE input_id = %s AND timestamp >= %s AND timestamp <= %s
                    ORDER BY timestamp ASC
                """, (input_id, start_ts, now_ts))
                events = cursor.fetchall()

                on_secs = 0.0
                off_secs = 0.0
                power_cuts = 0
                cur_state = initial_state
                cur_ts = start_ts

                for ev in events:
                    delta = ev['timestamp'] - cur_ts
                    if cur_state == 1:
                        on_secs += delta
                    else:
                        off_secs += delta
                    if ev['state'] == 0 and cur_state == 1:
                        power_cuts += 1
                    cur_state = ev['state']
                    cur_ts = ev['timestamp']

                delta = now_ts - cur_ts
                if cur_state == 1:
                    on_secs += delta
                else:
                    off_secs += delta

                result[input_id] = {
                    'on_seconds': max(on_secs, 0),
                    'off_seconds': max(off_secs, 0),
                    'power_cuts': power_cuts,
                    'since_hour': since_hour,
                }

            return result

        except Error as e:
            logger.error(f"Error getting daily summary: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

