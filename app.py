from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import threading

from handlers.lead_sync_handler import process_crm_lead_sync, process_vicidial_lead_sync
# from handlers.external_media_handler import meetme_join_handler, meetme_leave_handler
from services.ami_service import AMIService
# from services.ari_service import ARIService
from services.logger_service import logger

# Initialize AMI connection
ami = AMIService()
# ari = ARIService()
room_state = {}
room_lock = threading.Lock()

# High-concurrency worker thread pool
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


@ami.on("FullyBooted")
def boot(event):
    logger.info("Asterisk AMI Connection Fully Booted and Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_crm_lead_sync, event)


# @ami.on("MeetmeJoin")
# def handle_meetme_join(event):
#     """Triggered on conference join. Offloads lead sync and External Media concurrently."""
#     # Task 1: Process Vicidial Sync
#     executor.submit(process_vicidial_lead_sync, event)
    
#     # Task 2: Trigger External Media Streaming separately
#     executor.submit(meetme_join_handler, event)

@ami.on("MeetmeJoin")
def handle_meetme_join(event):
    channel = event.keys.get("Channel", "")
    meetme_room = event.keys.get("Meetme", "")
    caller_id = event.keys.get("CallerIDNum", "")
    unique_id = event.keys.get("Uniqueid", "")

    if not channel or not meetme_room:
        return

    is_agent = channel.startswith("Local/") or caller_id == "ding"

    with room_lock:
        if meetme_room not in room_state:
            room_state[meetme_room] = {}

        if is_agent:
            # Store Agent details
            room_state[meetme_room]["agent"] = {
                "channel": channel,
                "uniqueid": unique_id
            }
        else:
            # Customer joined: combine both channel details
            room_state[meetme_room]["customer"] = {
                "channel": channel,
                "uniqueid": unique_id
            }
            
            agent_data = room_state[meetme_room].get("agent")
            customer_data = room_state[meetme_room]["customer"]

            logger.info(
                f"FULL CONVERSATION CONNECTED | Room: {meetme_room} | "
                f"Agent Channel: {agent_data.get('channel') if agent_data else 'N/A'} | "
                f"Customer Channel: {customer_data['channel']}"
            )
    
# @ami.on("")
# def handle_meetme_leave(event):
#     executor.submit(meetme_leave_handler, event)
    
def shutdown(signum, frame):
    logger.info("Shutdown signal received. Shutting down Server 1 manager...")
    # 1. Stop listening to new AMI/ARI events
    try:
        # ari.stop()
        ami.disconnect()
    except Exception:
        logger.exception("Error disconnecting AMI")
    
    # 2. Drain worker pool (cancel non-started jobs, don't block indefinitely)
    executor.shutdown(wait=False)
    
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        # Initialize Asterisk ARI Service
        # ari.start()
        
        # Initialize Asterisk AMI Service
        ami.start()
    except KeyboardInterrupt:
        shutdown(None, None)