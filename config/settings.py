from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    AMI_HOST = os.getenv("AMI_HOST")
    AMI_PORT = int(os.getenv("AMI_PORT", 5038))
    AMI_USERNAME = os.getenv("AMI_USERNAME")
    AMI_PASSWORD = os.getenv("AMI_PASSWORD")

    VICIDIAL_DB_HOST = os.getenv("VICIDIAL_DB_HOST")
    VICIDIAL_DB_PORT = int(os.getenv("VICIDIAL_DB_PORT", 3306))
    VICIDIAL_DB_NAME = os.getenv("VICIDIAL_DB_NAME")
    VICIDIAL_DB_USER = os.getenv("VICIDIAL_DB_USER")
    VICIDIAL_DB_PASSWORD = os.getenv("VICIDIAL_DB_PASSWORD")

    API_BASE_URL = os.getenv("API_BASE_URL")
    API_TOKEN = os.getenv("API_TOKEN")


settings = Settings()
