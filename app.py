from concurrent.futures import ThreadPoolExecutor
import re
import signal
import sys

from handlers.customer_lookup_handler import process_customer_lookup
from handlers.external_media_handler import get_channel_var, process_bridge_end, process_bridge_start
from services.ami_service import AMIService
from services.ari_service import start_ari_service
from services.logger_service import logger

# Initialize AMI connection
ami = AMIService()

# High-concurrency worker thread pool
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


def is_internal_channel(channel: str, caller_id_num: str, caller_id_name: str) -> bool:
    """Helper to identify non-customer internal channels and VICIdial audio prompts."""
    return "Local/" in channel or caller_id_num == "ding" or caller_id_name == "ding"


def resolve_lead_id(ami_client, channel_name, caller_id_name, caller_id_num):
    """
    Attempts to fetch lead_id directly from Asterisk channel variables via AMI GetVar.
    Falls back to regex extraction from CallerID if AMI variables return empty.
    """
    # 1. Primary: Attempt AMI GetVar lookup on known VICIdial channel variables
    for var in ["vendor_lead_code", "VENDER_LEAD_CODE", "lead_id", "VICI_LEAD_ID"]:
        fetched_val = get_channel_var(ami_client, channel_name, var)
        if fetched_val and fetched_val.strip() and fetched_val != "0":
            return fetched_val.strip()

    # 2. Secondary Fallback: Regex extraction from CallerIDName (e.g., Y9080654360000000040)
    match = re.search(r'Y(\d{9,10})', caller_id_name or "")
    if match:
        return match.group(1)

    # 3. Tertiary Fallback: Check numeric CallerID
    if caller_id_num and caller_id_num.isdigit() and len(caller_id_num) >= 8:
        return caller_id_num

    return "UNKNOWN_LEAD"


@ami.on("FullyBooted")
def boot(event):
    logger.info("Asterisk AMI Connection Fully Booted and Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_customer_lookup, event)


@ami.on("MeetmeJoin")
def handle_meetme_join(event):
    event_keys = getattr(event, "keys", {})
    channel = event_keys.get("Channel", "")
    caller_id_num = event_keys.get("CallerIDNum", "")
    caller_id_name = event_keys.get("CallerIDName", "")
    meetme_room = event_keys.get("Meetme", "")
    unique_id = event_keys.get("Uniqueid", "")

    if is_internal_channel(channel, caller_id_num, caller_id_name):
        logger.debug(f"Ignoring internal join channel: {channel}")
        return

    # Fetch lead_id using AMI GetVar helper with fallback logic
    lead_id = resolve_lead_id(ami.client, channel, caller_id_name, caller_id_num)
    session_id = f"{meetme_room}_{lead_id}"

    # Determine participant role
    role = "agent" if "SIP/" in channel and not "ATnT" in channel and not "Trunk" in channel else "customer"
    assigned_port = 20002 if role == "agent" else 20004

    logger.debug(
        f"[ExternalMedia Prepared] "
        f"SessionID={session_id} | "
        f"Room={meetme_room} | "
        f"LeadID={lead_id} | "
        f"Role={role} | "
        f"TargetPort={assigned_port} | "
        f"Channel={channel} | "
        f"UniqueID={unique_id}"
    )

    logger.info(f"MeetmeJoin event detected: Room={meetme_room}, SessionID={session_id}, Channel={channel}")
    # Handlers disabled: executor.submit(process_bridge_start, event, ami.client)


@ami.on("MeetmeLeave")
def handle_meetme_leave(event):
    event_keys = getattr(event, "keys", {})
    channel = event_keys.get("Channel", "")
    caller_id_num = event_keys.get("CallerIDNum", "")
    caller_id_name = event_keys.get("CallerIDName", "")
    meetme_room = event_keys.get("Meetme", "")
    unique_id = event_keys.get("Uniqueid", "")

    if is_internal_channel(channel, caller_id_num, caller_id_name):
        return

    # Fetch lead_id using AMI GetVar helper with fallback logic
    lead_id = resolve_lead_id(ami.client, channel, caller_id_name, caller_id_num)
    session_id = f"{meetme_room}_{lead_id}"

    logger.debug(
        f"[ExternalMedia Teardown Logged] "
        f"SessionID={session_id} | "
        f"Room={meetme_room} | "
        f"LeadID={lead_id} | "
        f"Channel={channel} | "
        f"UniqueID={unique_id}"
    )

    logger.info(f"MeetmeLeave event detected: Room={meetme_room}, SessionID={session_id}, Channel={channel}")
    # Handlers disabled: executor.submit(process_bridge_end, event, ami.client)


@ami.on("Hangup")
def handle_hangup(event):
    executor.submit(process_bridge_end, event, ami.client)


def shutdown(signum, frame):
    logger.info("Shutdown signal received. Shutting down Server 1 manager...")
    executor.shutdown(wait=False)
    try:
        ami.disconnect()
    except Exception:
        logger.exception("Error disconnecting AMI")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Initialize Asterisk ARI Service
    start_ari_service()

    try:
        ami.start()
    except KeyboardInterrupt:
        shutdown(None, None)