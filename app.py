from concurrent.futures import ThreadPoolExecutor
import signal
import sys

from services.ami_service import AMIService
from services.logger_service import logger
from handlers.call_handlers import process_customer_lookup, process_bridge_start

# Initialize AMI connection
ami = AMIService()

# High-concurrency worker thread pool (adjust workers based on server specs)
executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="ami_worker")


@ami.on("FullyBooted")
def boot(event):
    logger.debug("Asterisk Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    """Triggered on incoming callers. Offloaded to worker pool."""
    executor.submit(process_customer_lookup, event)


@ami.on("BridgeEnter")
def handle_bridge_enter(event):
    """Triggered when agent bridges with caller. Offloaded to worker pool."""
    executor.submit(process_bridge_start, event, ami.client)


def shutdown(signum, frame):
    logger.info("Shutdown signal received. Closing application...")

    # Stop accepting new tasks and release threads
    executor.shutdown(wait=False)

    try:
        # Close AMI connection
        ami.disconnect()
    except Exception:
        logger.exception("Error while stopping AMI")

    logger.info("Application stopped successfully.")
    sys.exit(0)


if __name__ == "__main__":
    # Handle Ctrl+C and systemd/docker stop
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        ami.start()
    except KeyboardInterrupt:
        shutdown(None, None)
