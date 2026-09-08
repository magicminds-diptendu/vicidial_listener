import requests
from asterisk.ami import SimpleAction
from config.settings import settings
from services.ari_service import setup_single_channel_stream
from services.logger_service import logger

STT_SERVER_IP = getattr(settings, "STT_SERVER_IP", "192.168.1.100")
STT_INIT_URL = f"http://{STT_SERVER_IP}:5000/session/init"
STT_CLOSE_URL = f"http://{STT_SERVER_IP}:5000/session/close"

# Persistent HTTP Session for connection pooling
http_session = requests.Session()

# Track active call sessions and streamed channels separately
active_sessions = set()
active_channels = set()


def get_channel_var(ami_client, channel_name, variable_name):
    """Safely fetch channel variable using AMI GetVar."""
    try:
        action = SimpleAction("GetVar", Channel=channel_name, Variable=variable_name)
        response = ami_client.send_action(action)
        if response and response.response == "Success":
            return response.get_header("Value")
    except Exception:
        logger.exception(
            f"Failed to fetch variable '{variable_name}' from channel '{channel_name}'"
        )
    return None


def fetch_vicidial_metadata(ami_client, channel_name, event):
    """Fetches ViciDial lead and campaign metadata using event keys and channel memory."""
    caller_id_name = event.keys.get("CallerIDName", "")
    lead_id = None
    if caller_id_name.startswith("Y") and len(caller_id_name) >= 10:
        lead_id = caller_id_name[1:10].lstrip("0")

    if not lead_id:
        lead_id = get_channel_var(ami_client, channel_name, "VNDR_LEAD_ID") or get_channel_var(
            ami_client, channel_name, "lead_id"
        )

    return {
        "lead_id": lead_id,
        "vendor_lead_code": get_channel_var(ami_client, channel_name, "vendor_lead_code"),
        "campaign_id": get_channel_var(ami_client, channel_name, "CAMPAIGN"),
        "phone_number": event.keys.get("CallerIDNum")
        or get_channel_var(ami_client, channel_name, "phone_number"),
        "uniqueid": event.keys.get("Uniqueid")
        or get_channel_var(ami_client, channel_name, "UNIQUEID"),
        "meetme_room": event.keys.get("Meetme", ""),
    }


def process_bridge_start(event, ami_client):
    """Handles individual channel audio hook for both Agent and Customer legs."""
    channel = event.keys.get("Channel", "")
    if not channel or "Local/" in channel or channel in active_channels:
        return

    metadata = fetch_vicidial_metadata(ami_client, channel, event)
    uniqueid = metadata.get("uniqueid")

    if not uniqueid:
        return

    active_channels.add(channel)

    # Differentiate Customer vs Agent leg
    # (Adjust 'SIP/ATnT' or carrier check according to your environment)
    is_customer = "ATnT" in channel or not channel.startswith("SIP/")
    target_port = 20000 if is_customer else 20002
    role = "customer" if is_customer else "agent"

    # Fetch channel SSRC from Asterisk RTP state (or pass None if relying on dynamic fallback)
    ssrc = get_channel_var(ami_client, channel, "CHANNEL(rtp,ssrc)")

    # Send /session/init to Server 2 only once per call uniqueid
    if uniqueid not in active_sessions:
        active_sessions.add(uniqueid)
        init_payload = {
            "uniqueid": uniqueid,
            "metadata": metadata,
            "customer_ssrc": ssrc if is_customer else None,
            "agent_ssrc": ssrc if not is_customer else None,
        }
        try:
            http_session.post(STT_INIT_URL, json=init_payload, timeout=2)
            logger.info(f"Initialized STT session on Server 2 for {role} uniqueid: {uniqueid}")
        except Exception:
            logger.exception("Failed to send /session/init payload to Server 2")

    # Start ExternalMedia RTP Stream for this channel leg
    try:
        # setup_single_channel_stream(
        #     channel_id=channel,
        #     target_port=target_port,
        #     role=role,
        #     uniqueid=uniqueid,
        #     stt_server_ip=STT_SERVER_IP,
        # )
        logger.info(f"Hooked {role} RTP stream: Channel={channel} -> UDP {STT_SERVER_IP}:{target_port}")
    except Exception:
        logger.exception(f"Failed to setup {role} audio stream for channel {channel}")
        active_channels.discard(channel)


def process_bridge_end(event, ami_client):
    """Cleanup session tracking when call legs disconnect."""
    try:
        channel = event.keys.get("Channel", "")
        if not channel or "Local/" in channel:
            return

        uniqueid = event.keys.get("Uniqueid") or get_channel_var(ami_client, channel, "UNIQUEID")

        if channel in active_channels:
            active_channels.remove(channel)

        # Trigger session close on Server 2 when all legs hang up
        if uniqueid and uniqueid in active_sessions:
            active_sessions.remove(uniqueid)
            try:
                http_session.post(STT_CLOSE_URL, json={"uniqueid": uniqueid}, timeout=2)
                logger.info(f"Closed STT session stream on Server 2 for UniqueID: {uniqueid}")
            except Exception:
                logger.exception("Failed to send /session/close to Server 2")

    except Exception:
        logger.exception("Failed in process_bridge_end execution")