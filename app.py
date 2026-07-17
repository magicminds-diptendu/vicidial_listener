import signal
import sys

from services.ami_service import AMIService
from services.customer_service import CustomerService
from services.vicidial_service import VicidialService
from services.logger import logger

ami = AMIService()
customer_service = CustomerService()
vicidial_service = VicidialService()


@ami.on("FullyBooted")
def boot(event):
    logger.debug("Asterisk Ready")


@ami.on("NewCallerid")
def handle_new_call(event):
    logger.debug("Incoming call")

    try:
        channel = event.keys.get("Channel", "")
        phone = event.keys.get("CallerIDNum", "")

        # Ignore VICIdial internal Local channels
        if channel.startswith("Local/"):
            return
        # Ignore non-numeric caller IDs
        if not phone.isdigit():
            return
        
        # Ignore numbers like 0, 0000, 0000000000
        if set(phone) == {"0"}:
            return

        logger.debug(f"Customer Phone: {phone}")

        customer = customer_service.get_customer(phone)

        if customer:
            comments = (
                f"Email Address: {customer.get('email', '')}\n"
                f"Bank Name: {customer.get('bank_name', '')}\n"
                f"Phone Number: {customer.get('phone', '')}"
            )

            logger.debug(f"Customers Info: {comments}")

            vicidial_service.update_list(
                phone_number=phone,
                email=customer.get("email"),
                comments=comments,
            )
            logger.info(f"Customer Info Updated: {phone}")
        else:
            logger.info("Skipping VICIdial update. Customer not found.")

    except Exception as e:
        logger.exception("Customer API request failed")



def shutdown(signum, frame):
    logger.info("Shutdown signal received. Closing application...")

    try:
        # Close AMI connection
        ami.disconnect()
    except Exception:
        logger.exception("Error while stopping AMI")

    try:
        vicidial_service.close()
    except Exception:
        logger.exception("Error while closing VICIdial database")

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
