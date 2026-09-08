from concurrent.futures import ThreadPoolExecutor
import signal
import sys

from handlers.customer_lookup_handler import process_customer_lookup
# from handlers.external_media_handler import get_channel_var, process_bridge_end, process_bridge_start
from services.ami_service import AMIService
from services.ari_service import ARIService
from services.logger_service import logger

# Initialize AMI connection
ami = AMIService()
ari = ARIService()

# High-concurrency worker thread pool
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


@ami.on("FullyBooted")
def boot(event):
    logger.info("Asterisk AMI Connection Fully Booted and Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_customer_lookup, event)


def shutdown(signum, frame):
    logger.info("Shutdown signal received. Shutting down Server 1 manager...")
    executor.shutdown(wait=False)
    try:
        ari.stop()
        ami.disconnect()
    except Exception:
        logger.exception("Error disconnecting AMI")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        # Initialize Asterisk ARI Service
        ari.start()
        
        # Initialize Asterisk AMI Service
        ami.start()
    except KeyboardInterrupt:
        shutdown(None, None)