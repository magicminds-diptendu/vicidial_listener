from concurrent.futures import ThreadPoolExecutor
import signal
import sys

from handlers.lead_sync_handler import process_crm_lead_sync, process_vicidial_lead_sync
from handlers.external_media_handler import meetme_join_handler, meetme_leave_handler
from services.ami_service import AMIService
# from services.ari_service import ARIService
from services.logger_service import logger

# Initialize AMI connection
ami = AMIService()
# ari = ARIService()

# High-concurrency worker thread pool
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


@ami.on("FullyBooted")
def boot(event):
    logger.info("Asterisk AMI Connection Fully Booted and Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_crm_lead_sync, event)


@ami.on("MeetmeJoin")
def handle_meetme_join(event):
    """Triggered on conference join. Offloads lead sync and External Media concurrently."""
    # Task 1: Process Vicidial Sync
    executor.submit(process_vicidial_lead_sync, event)
    
    # Task 2: Trigger External Media Streaming separately
    executor.submit(meetme_join_handler, event)
    
@ami.on("")
def handle_meetme_leave(event):
    executor.submit(meetme_leave_handler, event)
    
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