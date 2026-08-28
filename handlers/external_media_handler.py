import requests
from asterisk.ami import SimpleAction
from config.settings import settings
from services.logger_service import logger

# Address of Server 2 (STT & Deepgram Pipeline Node)
STT_SERVER_IP = getattr(settings, "STT_SERVER_IP", "192.168.1.100")
STT_METADATA_URL = f"http://{STT_SERVER_IP}:5000/session/init"

# Asterisk ARI Configuration on Server 1 (Localhost)
ARI_BASE_URL = getattr(settings, "ARI_BASE_URL", "http://127.0.0.1:8088/ari")
ARI_AUTH = (
    getattr(settings, "ARI_USER", "deepgram_bridge"),
    getattr(settings, "ARI_PASS", "your_secure_ari_password")
)


def get_channel_var(ami_client, channel_name, variable_name):
    """Utility function to safely execute AMI GetVar using SimpleAction."""
    try:
        action = SimpleAction('GetVar', Channel=channel_name, Variable=variable_name)
        response = ami_client.send_action(action)
        if response and response.response == 'Success':
            return response.get_header('Value')
    except Exception:
        logger.exception(f"Failed to fetch variable '{variable_name}' from channel '{channel_name}'")
    return None


def fetch_vicidial_metadata(ami_client, channel_name):
    """Fetches ViciDial lead and campaign metadata from the customer channel."""
    lead_id = get_channel_var(ami_client, channel_name, "VNDR_LEAD_ID") or get_channel_var(ami_client, channel_name, "lead_id")
    vendor_code = get_channel_var(ami_client, channel_name, "vendor_lead_code")
    campaign_id = get_channel_var(ami_client, channel_name, "CAMPAIGN")
    phone_number = get_channel_var(ami_client, channel_name, "phone_number")
    uniqueid = get_channel_var(ami_client, channel_name, "UNIQUEID")

    return {
        "lead_id": lead_id,
        "vendor_lead_code": vendor_code,
        "campaign_id": campaign_id,
        "phone_number": phone_number,
        "uniqueid": uniqueid
    }


def process_bridge_start(event, ami_client):
    """Worker task: Captures bridged call metadata and triggers media export to Server 2."""
    try:
        channel_cust = event.keys.get("Channel", "")
        channel_agent = event.keys.get("DestinationChannel", "") or event.keys.get("ConnectedLineNum", "")

        # Filter out non-SIP channels or internal ViciDial dummy calls
        if not channel_cust or channel_cust.startswith("Local/"):
            return

        logger.info(f"Processing Bridge Start: Customer ({channel_cust}) <-> Agent ({channel_agent})")

        # 1. Pull ViciDial metadata from channel memory
        metadata = fetch_vicidial_metadata(ami_client, channel_cust)
        uniqueid = metadata.get("uniqueid")

        if not uniqueid:
            logger.warning(f"Could not retrieve UNIQUEID for channel {channel_cust}. Skipping STT.")
            return

        logger.info(f"ViciDial Metadata Captured: {metadata}")

        # 2. Register session metadata on Server 2 (Flask API)
        try:
            requests.post(
                STT_METADATA_URL,
                json={"uniqueid": uniqueid, "metadata": metadata},
                timeout=2
            )
            logger.debug(f"Pushed session metadata to STT Server: {uniqueid}")
        except Exception:
            logger.exception("Failed to connect to Server 2 STT Metadata API")

        # 3. Request External Media for Customer (RTP -> Server 2 Port 20000)
        requests.post(
            f"{ARI_BASE_URL}/channels/externalMedia",
            params={"app": "deepgram_bridge", "external_host": f"{STT_SERVER_IP}:20000", "format": "slin16"},
            auth=ARI_AUTH,
            timeout=2
        )

        # 4. Request External Media for Agent (RTP -> Server 2 Port 20002)
        requests.post(
            f"{ARI_BASE_URL}/channels/externalMedia",
            params={"app": "deepgram_bridge", "external_host": f"{STT_SERVER_IP}:20002", "format": "slin16"},
            auth=ARI_AUTH,
            timeout=2
        )

        # 5. Attach Snoop channels in Asterisk to route audio into External Media
        requests.post(
            f"{ARI_BASE_URL}/channels/{channel_cust}/snoop",
            params={"app": "deepgram_bridge", "spy": "in", "snoop_id": f"snoop_cust_{uniqueid}"},
            auth=ARI_AUTH,
            timeout=2
        )

        requests.post(
            f"{ARI_BASE_URL}/channels/{channel_agent}/snoop",
            params={"app": "deepgram_bridge", "spy": "out", "snoop_id": f"snoop_agent_{uniqueid}"},
            auth=ARI_AUTH,
            timeout=2
        )

        logger.info(f"Successfully initiated external media streams to Server 2 ({STT_SERVER_IP}) for call {uniqueid}")

    except Exception:
        logger.exception("Failed in process_bridge_start execution")