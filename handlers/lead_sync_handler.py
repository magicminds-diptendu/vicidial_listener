from services.lead_sync_service import LeadSyncService
from services.logger_service import logger
from services.vicidial_service import VicidialService
from config.settings import settings
import requests

lead_sync_service = LeadSyncService()
vicidial_service = VicidialService()

def refresh_agent_screen(user: str, lead_id: int) -> bool:
    """
    Forces the active Vicidial agent screen to instantly refresh and re-fetch 
    lead details from the database after a DB update.
    """
    api_url = f"http://{settings.AMI_HOST}/agc/api.php"
    
    payload = {
        "source": "python_listener",
        "user": settings.AMI_USERNAME,      # Vicidial API Admin user
        "pass": settings.AMI_PASSWORD,      # Vicidial API Admin pass
        "agent_user": user,                 # Active Vicidial agent ID (e.g. "1001")
        "function": "ra_call_control",
        "stage": "RE-LOCATION",
        "value": lead_id,
    }

    try:
        logger.info(f"Sending refresh command for Agent '{user}' on Lead ID '{lead_id}'")
        response = requests.get(api_url, params=payload, timeout=5)
        
        if response.status_code == 200 and "SUCCESS" in response.text:
            logger.info(f"Agent screen refreshed successfully: {response.text.strip()}")
            return True
        
        logger.warning(f"Vicidial API returned non-success response: {response.text.strip()}")
        return False
        
    except requests.RequestException as e:
        logger.error(f"Failed to trigger agent screen refresh: {e}")
        return False


def process_lead_sync(event):
    """Worker task: Fetches lead details and updates VICIdial asynchronously."""
    try:
        channel = event.keys.get("Channel", "")
        phone = event.keys.get("CallerIDNum", "")

        # Ignore VICIdial internal Local channels
        if channel.startswith("Local/"):
            return
        # Ignore non-numeric caller IDs
        if not phone.isdigit():
            return
        # Ignore dummy numbers like 0, 0000, 0000000000
        if set(phone) == {"0"}:
            return

        logger.debug(f"Processing Lead Phone: {phone}")

        lead_synced = lead_sync_service.sync_vicidial_lead_info(phone)

        if lead_synced:
            logger.info(f"Lead Info Synced: {phone}")
            
        else:
            logger.info(f"Skipping VICIdial update. Lead not found for {phone}")

    except Exception:
        logger.exception("Lead Sync request failed")
