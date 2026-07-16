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

    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("VICIdial database connection closed")
