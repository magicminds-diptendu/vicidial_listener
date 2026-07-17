import pymysql
from config.settings import settings
from services.logger import logger


class VicidialService:
    def __init__(self):
        self.connection = None

    def connect(self):
        """Create a database connection if needed."""
        if self.connection and self.connection.open:
            return

        self.connection = pymysql.connect(
            host=settings.VICIDIAL_DB_HOST,
            port=settings.VICIDIAL_DB_PORT,
            user=settings.VICIDIAL_DB_USER,
            password=settings.VICIDIAL_DB_PASSWORD,
            database=settings.VICIDIAL_DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

        logger.info("Connected to VICIdial database")

    def execute(self, query, params=None):
        self.connect()

        with self.connection.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def execute_one(self, query, params=None):
        self.connect()

        with self.connection.cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()

    def update(self, query, params=None):
        self.connect()

        with self.connection.cursor() as cursor:
            affected = cursor.execute(query, params or ())
            return affected

    def update_list(self, phone_number, **fields):
        lead = self.execute_one(
            """
            SELECT lead_id
            FROM vicidial_list
            WHERE phone_number = %s
            ORDER BY lead_id DESC
            LIMIT 1
            """,
            (phone_number,),
        )

        if not lead:
            logger.warning(f"No VICIdial lead found for {phone_number}")
            return False

        if not fields:
            logger.warning("No fields provided to update.")
            return False

        lead_id = lead["lead_id"]

        set_clause = ", ".join(f"{column}=%s" for column in fields.keys())
        values = list(fields.values()) + [lead_id]

        query = f"""
            UPDATE vicidial_list
            SET {set_clause}
            WHERE lead_id = %s
        """

        self.update(query, values)

        logger.info(f"Updated lead {lead_id} with fields: {list(fields.keys())}")
        return True

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("VICIdial database connection closed")
