from asterisk.ami import SimpleAction
from config.settings import settings
from services.customer_service import CustomerService
from services.logger_service import logger
from services.vicidial_service import VicidialService

customer_service = CustomerService()
vicidial_service = VicidialService()


def process_customer_lookup(event):
    """Worker task: Fetches customer details and updates VICIdial asynchronously."""
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

        logger.debug(f"Processing Customer Phone: {phone}")

        customer = customer_service.get_customer(phone)

        if customer:
            comments = (
                f"Email Address: {customer.get('email', '')}\n"
                f"Bank Name: {customer.get('bank_name', '')}\n"
                f"Phone Number: {customer.get('phone', '')}"
            )

            vicidial_service.update_list(
                phone_number=phone,
                email=customer.get("email"),
                comments=comments,
            )
            logger.info(f"Customer Info Updated: {phone}")
        else:
            logger.info(f"Skipping VICIdial update. Customer not found for {phone}")

    except Exception:
        logger.exception("Customer API/DB request failed")
