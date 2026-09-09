from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    AMI_HOST = os.getenv("AMI_HOST", "127.0.0.1")
    AMI_PORT = int(os.getenv("AMI_PORT", 5038))
    AMI_USERNAME = os.getenv("AMI_USERNAME", "listencron")
    AMI_PASSWORD = os.getenv("AMI_PASSWORD", "1234")

    VICIDIAL_DB_HOST = os.getenv("VICIDIAL_DB_HOST", "127.0.0.1")
    VICIDIAL_DB_PORT = int(os.getenv("VICIDIAL_DB_PORT", 3306))
    VICIDIAL_DB_NAME = os.getenv("VICIDIAL_DB_NAME", "asterisk")
    VICIDIAL_DB_USER = os.getenv("VICIDIAL_DB_USER", "cron")
    VICIDIAL_DB_PASSWORD = os.getenv("VICIDIAL_DB_PASSWORD", "1234")

    ARI_HOST = os.getenv("ARI_HOST", "127.0.0.1")
    ARI_PORT = int(os.getenv("ARI_PORT", 8088))
    ARI_USER = os.getenv("ARI_USER")
    ARI_PASS = os.getenv("ARI_PASS")

    STT_SERVER_IP = os.getenv('STT_SERVER_IP')
    STT_INIT_URL = os.getenv('STT_INIT_URL')
    STT_CLOSE_URL = os.getenv('STT_CLOSE_URL')
    
    VENDOR_WEBHOOK_URL = os.getenv("VENDOR_WEBHOOK_URL")
    
    CRM_WEBHOOK_URL = os.getenv("CRM_WEBHOOK_URL")


settings = Settings()
