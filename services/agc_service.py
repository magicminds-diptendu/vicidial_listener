import requests
import urllib3
from typing import Dict, Any 
from config.settings import settings
from services.logger_service import logger

# Suppress self-signed / IP mismatch SSL warnings for local requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AGCService:
    def __init__(self):
        self.api_url = settings.VICIDIAL_API_ENDPOINT
        self.username = settings.VICIDIAL_API_USER
        self.password = settings.VICIDIAL_API_PASS
        
    def update_agent_lead_fields(self, agent_user: str, lead_id: int, contact: Dict[str, Any]) -> bool:
        """
        Updates active agent lead fields in real-time via agc/api.php
        """
        
        # 1. Filter out None values so we only send populated fields
        filtered_fields = {k: v for k, v in contact.items() if v is not None}

        # 2. Construct payload matching your working curl POST structure
        payload = {
            "source": "python_listener",
            "user": self.username,
            "pass": self.password,
            "function": "update_fields",
            "agent_user": agent_user,
            "value": lead_id,
            **filtered_fields
        }

        try:
            logger.info(
                f"Sending refresh command for Agent '{agent_user}' on Lead ID '{lead_id}'"
            )
            
            response = requests.post(
                self.api_url,
                data=payload,
                verify=False,
                timeout=5
            )

            response_text = response.text.strip()
            if response.status_code == 200 and "SUCCESS" in response_text:
                logger.info(
                    f"Agent lead updated successfully: {response.text.strip()}"
                )
                
                return True
            
            logger.warning(
                f"Vicidial API returned non-success response: {response.text.strip()}"
            )

            return False

        except requests.RequestException:
            return False
