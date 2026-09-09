from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

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

    ARI_BASE_URL = os.getenv("ARI_BASE_URL")
    ARI_USER = os.getenv("ARI_USER")
    ARI_PASS = os.getenv("ARI_PASS")

    STT_SERVER_IP = os.getenv('STT_SERVER_IP')
    STT_INIT_URL = os.getenv('STT_INIT_URL')
    STT_CLOSE_URL = os.getenv('STT_CLOSE_URL')
    UDP_CUSTOMER_PORT = int(os.getenv('UDP_CUSTOMER_PORT'))
    UDP_AGENT_PORT = int(os.getenv('UDP_AGENT_PORT'))


settings = Settings()
