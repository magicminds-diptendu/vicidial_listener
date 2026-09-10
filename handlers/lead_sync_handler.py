from services.lead_sync_service import LeadSyncService
from services.logger_service import logger
from services.vicidial_service import VicidialService

lead_sync_service = LeadSyncService()
vicidial_service = VicidialService()


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
