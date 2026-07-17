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
    logger.info("ASTERISK READY")


@ami.on("NewCallerid")
def handle_new_call(event):
    logger.info("Incoming call")
    logger.info(event.keys)

    try:
        channel = event.get("Channel", "")
        phone = event.get("CallerIDNum", "")

        # Ignore VICIdial internal Local channels
        if channel.startswith("Local/"):
            return

        # Ignore non-numeric caller IDs
        if not phone.isdigit():
            return

        logger.info(f"Customer Phone: {phone}")

        customer = customer_service.get_customer(phone)

        if customer:
            comments = (
                f"Email Address: {customer.get('email', '')}\n"
                f"Bank Name: {customer.get('bank_name', '')}\n"
                f"Phone Number: {customer.get('phone', '')}"
            )

            logger.info(f"Customers Info: {comments}")

            lead = vicidial_service.execute_one(
                """
                SELECT *
                FROM vicidial_list
                WHERE phone_number = %s
                ORDER BY lead_id DESC
                LIMIT 1
                """,
                (phone,),
            )

            if not lead:
                logger.warning(f"No VICIdial lead found for {phone}")
            else:
                logger.info("Vicidial List info", lead)

            # vicidial_service.update_list(
            #     phone_number=phone,
            #     email=customer.get("email"),
            #     comments=comments,
            # )
            logger.info(f"Customer Info Updated: {phone}")
        else:
            logger.info("Skipping VICIdial update. Customer not found.")


    except Exception as e:
        logger.exception("Customer API request failed")


@ami.on("Hangup")
def handle_hangup(event):
    logger.info("Call Ended")
    logger.info(event.keys)


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
