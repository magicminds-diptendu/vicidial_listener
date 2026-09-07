import requests
from asterisk.ami import SimpleAction
from config.settings import settings
from services.logger_service import logger

# Address of Server 2 (STT & Deepgram Pipeline Node)
STT_SERVER_IP = getattr(settings, "STT_SERVER_IP", "192.168.1.100")
STT_INIT_URL = f"http://{STT_SERVER_IP}:5000/session/init"
STT_CLOSE_URL = f"http://{STT_SERVER_IP}:5000/session/close"

# Asterisk ARI Configuration on Server 1 (Localhost)
ARI_BASE_URL = getattr(settings, "ARI_BASE_URL", "http://127.0.0.1:8088/ari")
ARI_AUTH = (
    getattr(settings, "ARI_USER", "stt_service"),
    getattr(settings, "ARI_PASS", "your_secure_ari_password")
)

# Prevent duplicate STT initialization for the same call. 
active_stt_calls = set()


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
        
        if uniqueid in active_stt_calls: 
            logger.debug( f"STT already initialized for {uniqueid}. Ignoring duplicate BridgeEnter." ) 
            return 
        
        active_stt_calls.add(uniqueid)

        # 2. Register session metadata on Server 2 (Flask API)
        try:
            response = requests.post(
                STT_INIT_URL,
                json={"uniqueid": uniqueid, "metadata": metadata},
                timeout=2
            )

            response.raise_for_status()

            logger.debug(f"Pushed session metadata to STT Server: {uniqueid}")
        except Exception:
            active_stt_calls.discard(uniqueid)
            logger.exception("Failed to connect to Server 2 STT Metadata API")
            return

        # 3. Request External Media for Customer (RTP -> Server 2 Port 20000)
        customer_external_response = requests.post(
            f"{ARI_BASE_URL}/channels/externalMedia",
            params={"app": "stt_service", "external_host": f"{STT_SERVER_IP}:20000", "format": "slin16"},
            auth=ARI_AUTH,
            timeout=2
        )

        customer_external_response.raise_for_status()
        customer_external = customer_external_response.json()
        customer_external_id = customer_external.get("id")

        if not customer_external_id:
            raise RuntimeError(
                "ARI did not return customer ExternalMedia channel ID"
            )

        logger.info(f"Customer ExternalMedia created: {customer_external_id} -> {STT_SERVER_IP}:20000")

        # 4. Request External Media for Agent (RTP -> Server 2 Port 20002)
        agent_external_response = requests.post(
            f"{ARI_BASE_URL}/channels/externalMedia",
            params={"app": "stt_service", "external_host": f"{STT_SERVER_IP}:20002", "format": "slin16"},
            auth=ARI_AUTH,
            timeout=2
        )

        agent_external_response.raise_for_status()
        agent_external = agent_external_response.json()
        agent_external_id = agent_external.get("id")

        if not agent_external_id:
            raise RuntimeError(
                "ARI did not return agent ExternalMedia channel ID"
            )

        logger.info(f"Agent ExternalMedia created: {agent_external_id} -> {STT_SERVER_IP}:20002")

        # 5. Attach Snoop channels in Asterisk to route audio into External Media
        customer_snoop_response = requests.post(
            f"{ARI_BASE_URL}/channels/{channel_cust}/snoop",
            params={"app": "stt_service", "spy": "in", "snoop_id": f"snoop_cust_{uniqueid}"},
            auth=ARI_AUTH,
            timeout=2
        )

        customer_snoop_response.raise_for_status()
        customer_snoop = customer_snoop_response.json()
        customer_snoop_id = customer_snoop.get("id")

        if not customer_snoop_id:
            raise RuntimeError(
                "ARI did not return customer Snoop channel ID"
            )

        logger.info(f"Customer Snoop created: {customer_snoop_id}")

        agent_snoop_response = requests.post(
            f"{ARI_BASE_URL}/channels/{channel_agent}/snoop",
            params={"app": "stt_service", "spy": "out", "snoop_id": f"snoop_agent_{uniqueid}"},
            auth=ARI_AUTH,
            timeout=2
        )

        agent_snoop_response.raise_for_status()
        agent_snoop = agent_snoop_response.json()
        agent_snoop_id = agent_snoop.get("id")

        if not agent_snoop_id:
            raise RuntimeError(
                "ARI did not return agent Snoop channel ID"
            )

        logger.info(f"Agent Snoop created: {agent_snoop_id}")


        logger.info(
            f"STT media pipeline started for {uniqueid}: "
            f"customer={channel_cust} "
            f"-> snoop={customer_snoop_id} "
            f"-> external={customer_external_id} "
            f"-> {STT_SERVER_IP}:20000 | "
            f"agent={channel_agent} "
            f"-> snoop={agent_snoop_id} "
            f"-> external={agent_external_id} "
            f"-> {STT_SERVER_IP}:20002"
        )

    except Exception:
        logger.exception("Failed in process_bridge_start execution")
        
        # If we know the uniqueid, allow a future BridgeEnter 
        # to retry initialization. 
        try: 
            if uniqueid: 
                active_stt_calls.discard(uniqueid) 
                
        except UnboundLocalError: 
            pass


def process_bridge_end(event, ami_client):
    """Worker Task: Triggered on BridgeLeave or Hangup -> Calls /session/close"""
    try:
        channel = event.keys.get("Channel", "")
        if not channel or channel.startswith("Local/"):
            return

        uniqueid = event.keys.get("Uniqueid") or get_channel_var(ami_client, channel, "UNIQUEID")
        if not uniqueid:
            return

        # TRIGGER /session/close ON SERVER 2
        try:
            requests.post(STT_CLOSE_URL, json={"uniqueid": uniqueid}, timeout=2)
            logger.info(f"Closed session on Server 2 for UniqueID: {uniqueid}")
        except Exception:
            logger.exception("Failed to send /session/close to Server 2")

    except Exception:
        logger.exception("Failed in process_bridge_end execution")