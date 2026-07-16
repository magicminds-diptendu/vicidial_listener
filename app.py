from services.ami_service import AMIService
from services.customer_service import CustomerService
from services.logger import logger

ami = AMIService()
customer_service = CustomerService()


@ami.on("NewCallerid")
def handle_new_call(event):
    logger.info("Incoming call")
    logger.info(event.keys)

    try:
        result = customer_service.get_customer(event.keys)
        logger.info(f"Customer API Response: {result}")

    except Exception as e:
        logger.exception("Customer API request failed")


@ami.on("Hangup")
def handle_hangup(event):
    logger.info("Call Ended")
    logger.info(event.keys)


if __name__ == "__main__":
    ami.start()
