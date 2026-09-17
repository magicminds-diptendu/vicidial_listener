import requests
import urllib3
from config.settings import settings
from services.logger_service import logger

# Suppress self-signed / IP mismatch SSL warnings for local requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AGCService:
    def __init__(self):
        self.api_url = settings.VICIDIAL_API_ENDPOINT
        self.username = settings.VICIDIAL_API_USER
        self.password = settings.VICIDIAL_API_PASS

    def refresh_agent_screen(self, user: str, lead_id: int) -> bool:
        """
        Forces the active Vicidial agent screen to instantly refresh and re-fetch
        lead details from the database after a DB update.
        """

        payload = {
            "source": "python_listener",
            "user": self.username,
            "pass": self.password,
            "agent_user": user,
            "function": "ra_call_control",  # Updated from switch_lead
            "stage": "RE-LOCATION",         # Required stage for ra_call_control
            "value": lead_id,
        }

        try:
            logger.info(
                f"Sending refresh command for Agent '{user}' on Lead ID '{lead_id}'"
            )
            
            # verify=False prevents the SSLError on 127.0.0.1
            response = requests.get(
                self.api_url, 
                params=payload, 
                verify=False, 
                timeout=5
            )

            if response.status_code == 200 and "SUCCESS" in response.text:
                logger.info(
                    f"Agent screen refreshed successfully: {response.text.strip()}"
                )
                return True

            logger.warning(
                f"Vicidial API returned non-success response: {response.text.strip()}"
            )
            return False

        except requests.RequestException as e:
            logger.error(f"Failed to trigger agent screen refresh: {e}")
            return False