from concurrent.futures import ThreadPoolExecutor
import signal
import sys

from handlers.customer_lookup_handler import process_customer_lookup
from handlers.external_media_handler import process_bridge_end, process_bridge_start
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

    if is_internal_channel(channel, caller_id_num, caller_id_name):
        logger.debug(f"Ignoring internal join channel: {channel}")
        return

    logger.info(f"MeetmeJoin event detected: Room={meetme_room}, Channel={channel}")
    executor.submit(process_bridge_start, event, ami.client)


@ami.on("MeetmeLeave")
def handle_meetme_leave(event):
    event_keys = getattr(event, "keys", {})
    channel = event_keys.get("Channel", "")
    caller_id_num = event_keys.get("CallerIDNum", "")
    caller_id_name = event_keys.get("CallerIDName", "")

    if is_internal_channel(channel, caller_id_num, caller_id_name):
        return

    executor.submit(process_bridge_end, event, ami.client)


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