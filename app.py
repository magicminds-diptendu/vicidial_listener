from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import threading

from services.ami_service import AMIService
from services.logger_service import logger
from handlers.customer_lookup_handler import process_customer_lookup
from handlers.external_media_handler import process_bridge_start, process_bridge_end

# Initialize AMI connection
ami = AMIService()

# High-concurrency worker thread pool
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


def is_internal_channel(channel: str, caller_id_num: str, caller_id_name: str) -> bool:
    """Helper to identify non-customer internal channels and VICIdial ding sounds."""
    return "Local/" in channel or caller_id_num == "ding" or caller_id_name == "ding"


@ami.on("FullyBooted")
def boot(event):
    logger.debug("Asterisk Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_customer_lookup, event)


@ami.on("MeetmeJoin")
def handle_meetme_join(event):
    channel = event.keys.get("Channel", "")
    caller_id_num = event.keys.get("CallerIDNum", "")
    caller_id_name = event.keys.get("CallerIDName", "")
    meetme_room = event.keys.get("Meetme", "")

    # 1. Ignore internal audio and local channels
    if is_internal_channel(channel, caller_id_num, caller_id_name):
        logger.debug(f"Ignoring internal join channel: {channel}")
        return

    # 2. Process BOTH Agent and Customer connections
    if channel.startswith("SIP/") and not channel.startswith("SIP/ATnT"):
        logger.info(f"Agent joined room {meetme_room}: Channel={channel}")
    else:
        logger.info(f"Customer joined room {meetme_room}: Channel={channel}, Phone={caller_id_num}")

    # Offload to worker pool to start streaming RTP (Agent or Customer)
    executor.submit(process_bridge_start, event, ami.client)


@ami.on("MeetmeLeave")
def handle_meetme_leave(event):
    channel = event.keys.get("Channel", "")
    caller_id_num = event.keys.get("CallerIDNum", "")
    caller_id_name = event.keys.get("CallerIDName", "")
    meetme_room = event.keys.get("Meetme", "")

    # 1. Ignore internal audio and local channels
    if is_internal_channel(channel, caller_id_num, caller_id_name):
        logger.debug(f"Ignoring internal leave channel: {channel}")
        return

    # 2. Track disconnect for both Agent and Customer
    if channel.startswith("SIP/") and not channel.startswith("SIP/ATnT"):
        logger.info(f"Agent left room {meetme_room}: Channel={channel}")
    else:
        logger.info(f"Customer left room {meetme_room}: Channel={channel}")

    # Cleanup session streaming
    executor.submit(process_bridge_end, event, ami.client)


@ami.on("Hangup")
def handle_hangup(event):
    logger.debug("Hangup detected", extra={"event": event})
    executor.submit(process_bridge_end, event, ami.client)


def shutdown(signum, frame):
    logger.info("Shutdown signal received. Closing application...")

    executor.shutdown(wait=False)

    try:
        ami.disconnect()
    except Exception:
        logger.exception("Error while stopping AMI")

    logger.info("Application stopped successfully.")
    sys.exit(0)


def start_ari_service():
    """Starts the ARI WebSocket in a daemon thread."""
    ari_thread = threading.Thread(target=ami.run_ari_websocket, daemon=True, name="ari_stasis_ws")
    ari_thread.start()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Register ARI Stasis application with Asterisk
    start_ari_service()

    try:
        ami.start()
    except KeyboardInterrupt:
        shutdown(None, None)