from dbutils.pooled_db import PooledDB
import pymysql
from config.settings import settings
from services.logger_service import logger


class VicidialService:
    def __init__(self):
        self._pool = None
        self._init_pool()

    def _init_pool(self):
        """Initialize thread-safe PyMySQL database connection pool."""
        try:
            self._pool = PooledDB(
                creator=pymysql,
                mincached=5,  # Minimum idle connections created at start
                maxcached=20,  # Maximum idle connections kept in pool
                maxconnections=50,  # Maximum connections allowed across all threads
                blocking=True,  # Block threads if pool limit reached until connection frees
                host=settings.VICIDIAL_DB_HOST,
                port=settings.VICIDIAL_DB_PORT,
                user=settings.VICIDIAL_DB_USER,
                password=settings.VICIDIAL_DB_PASSWORD,
                database=settings.VICIDIAL_DB_NAME,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )
            logger.info("Initialized VICIdial database connection pool")
        except Exception:
            logger.exception("Failed to initialize VICIdial DB connection pool")

    def _get_connection(self):
        """Fetch a dedicated connection from the pool for the current thread."""
        return self._pool.connection()

    def execute_one(self, query, params=None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        finally:
            conn.close()

    def update(self, query, params=None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                return cursor.execute(query, params or ())
        finally:
            conn.close()
            
    def table_exists(self, table_name):
        """Check if a specific table exists in the current database schema."""
        query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """
        result = self.execute_one(query, (table_name,))
        return bool(result)

    def update_list(self, lead_id, **fields):
        """Update the vicidial_list table for a specific lead_id with provided fields."""
        if not fields:
            logger.warning("No fields provided to update.")
            return False
    
        set_clause = ", ".join(f"{column}=%s" for column in fields.keys())
        values = list(fields.values()) + [lead_id]

        query = f"""
            UPDATE vicidial_list
            SET {set_clause}
            WHERE lead_id = %s
        """

        self.update(query, values)
        logger.debug(f"Updated lead {lead_id} with fields: {list(fields.keys())}")
        return True
    
    def update_custom_fields(self, list_id, lead_id, **fields):
        """Update the custom_<list_id> table for a specific lead_id with provided fields."""
        if not fields:
            logger.warning("No fields provided to update.")
            return False

        custom_table_name = f"custom_{list_id}"
        table_exists = self.table_exists(custom_table_name)
        if not table_exists:
            logger.warning(f"Custom table {custom_table_name} does not exist. Skipping update.")
            return False
        
        set_clause = ", ".join(f"{column}=%s" for column in fields.keys())
        values = list(fields.values()) + [lead_id]

        query = f"""
            UPDATE `{custom_table_name}`
            SET {set_clause}
            WHERE lead_id = %s
        """

        self.update(query, values)
        logger.debug(f"Updated custom table {custom_table_name} for lead {lead_id} with fields: {list(fields.keys())}")
        return True

    def close(self):
        """Close pool resources on shutdown."""
        if self._pool:
            self._pool.close()
            self._pool = None
            logger.debug("VICIdial database connection pool closed")
