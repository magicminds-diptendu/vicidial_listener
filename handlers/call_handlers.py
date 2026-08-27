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


def process_bridge_start(event, ami_client):
    """
    Worker task:
    1. Triggers MixMonitor recording with auto S3/MinIO move on finish.
    2. Starts ExternalMedia streaming to Server 2 (STT Microservice).
    """
    try:
        channel = event.keys.get("Channel", "")
        linked_id = event.keys.get("Linkedid", "")

        # Ignore VICIdial local bridge channels to prevent duplicate actions
        if channel.startswith("Local/"):
            return

        filename = f"call_{linked_id}.wav"
        local_path = f"/tmp/{filename}"
        s3_destination = f"s3://{settings.S3_BUCKET_NAME}/recordings/{filename}"

        logger.info(f"Call bridged on channel {channel}. Initiating recording & media stream...")

        # 1. Trigger MixMonitor with Post-Hangup S3/MinIO Move Command
        mixmonitor_action = SimpleAction(
            "MixMonitor",
            Channel=channel,
            File=local_path,
            Options="b",  # Only record audio when bridged
            Command=f"aws s3 mv {local_path} {s3_destination} --endpoint-url {settings.MINIO_ENDPOINT_URL}",
        )
        ami_client.send_action(mixmonitor_action)
        logger.info(f"MixMonitor initiated for channel {channel}")

        # 2. Trigger ExternalMedia to stream live RTP audio to Server 2
        external_media_action = SimpleAction(
            "ExternalMedia",
            Channel=channel,
            External_host=f"{settings.STT_SERVER_IP}:{settings.STT_SERVER_PORT}",
            Format="slin16",
            Encapsulation="rtp",
        )
        ami_client.send_action(external_media_action)
        logger.info(f"ExternalMedia stream initiated from {channel} -> {settings.STT_SERVER_IP}")

    except Exception:
        logger.exception(f"Error handling BridgeEnter event for channel {event.keys.get('Channel')}")