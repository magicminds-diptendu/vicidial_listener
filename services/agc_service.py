import requests
from collections import defaultdict
from threading import Event
from asterisk.ami import AMIClient
from config.settings import settings
from services.logger_service import logger


class AGCService:
    def __init__(self):
        self.api_url = f"http://{settings.AMI_HOST}/agc/api.php"
        self.username = settings.AMI_USERNAME
        self.password = settings.AMI_PASSWORD

    def refresh_agent_screen(self, user: str, lead_id: int) -> bool:
        """
        Forces the active Vicidial agent screen to instantly refresh and re-fetch 
        lead details from the database after a DB update.
        """
        
        payload = {
            "source": "python_listener",
            "user": self.username,      # Vicidial API Admin user
            "pass": self.password,      # Vicidial API Admin pass
            "agent_user": user,                 # Active Vicidial agent ID (e.g. "1001")
            "function": "switch_lead",
            "value": lead_id,
        }

        try:
            logger.info(f"Sending refresh command for Agent '{user}' on Lead ID '{lead_id}'")
            response = requests.get(self.api_url, params=payload, timeout=5)
            
            if response.status_code == 200 and "SUCCESS" in response.text:
                logger.info(f"Agent screen refreshed successfully: {response.text.strip()}")
                return True
            
            logger.warning(f"Vicidial API returned non-success response: {response.text.strip()}")
            return False
            
        except requests.RequestException as e:
            logger.error(f"Failed to trigger agent screen refresh: {e}")
            return False

    