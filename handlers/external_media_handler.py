import threading
import time
import uuid
import urllib.parse
import requests
from services.logger_service import logger
from config.settings import settings

room_state = {}
room_lock = threading.Lock()
stt_api_endpoint = getattr(settings, "STT_API_ENDPOINT", "http://127.0.0.1:5000")

# Helper to centralize ARI credentials
def get_ari_config():
    ari_host = getattr(settings, "ARI_HOST", "127.0.0.1")
    ari_port = getattr(settings, "ARI_PORT", 8088)
    ari_user = getattr(settings, "ARI_USER", "stt_service")
    ari_password = getattr(settings, "ARI_PASS", "your_secure_ari_password")
    return (ari_user, ari_password), f"http://{ari_host}:{ari_port}/ari"


def generate_conversation_id(meetme_room: str) -> str:
    timestamp = int(time.time())
    short_hash = uuid.uuid4().hex[:6]
    return f"conv_{meetme_room}_{timestamp}_{short_hash}"

def init_stream_session(conversation_id: str, metadata: dict) -> dict:
    """
    Calls /session/init on StreamManager to register call state and allocate/return dynamic audio ports.
    
    Returns:
        dict containing allocated ports e.g., {"agent_port": 20002, "customer_port": 20000}
    """
    try:
        response = requests.post(
            f"{stt_api_endpoint}/session/init",
            json={
                "conversation_id": conversation_id,
                "metadata": metadata,
            },
            timeout=3,
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract ports dictionary from API response
        ports = data.get("ports", {})
        logger.info(f"StreamManager session initialized for {conversation_id}: {ports}")
        return ports
    
    except Exception as e:
        logger.error(f"Failed to initialize session on StreamManager for {conversation_id}: {e}")
        # Fallback default ports if API fails
        return {"agent_port": 10000, "customer_port": 10001}

def close_stream_session(conversation_id: str):
    """Calls /session/close on StreamManager to initiate session teardown."""
    try:
        response = requests.post(
            f"{stt_api_endpoint}/session/close",
            json={"conversation_id": conversation_id},
            timeout=3,
        )
        response.raise_for_status()
        logger.info(f"StreamManager session closed for {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to close session on StreamManager for {conversation_id}: {e}")

def process_meetme_join(event):
    event_data = dict(event.keys) if hasattr(event, "keys") else event

    channel = event_data.get("Channel", "")
    meetme_room = event_data.get("Meetme", "")
    caller_id = event_data.get("CallerIDNum", "")
    unique_id = event_data.get("Uniqueid", "")
    
    if channel.startswith("Local/"):
        return

    if not meetme_room:
        return

    is_agent = caller_id == "0000000000"

    with room_lock:
        if meetme_room not in room_state:
            room_state[meetme_room] = {}

        if is_agent:
            room_state[meetme_room]["agent"] = {
                "channel": channel,
                "uniqueid": unique_id,
            }
            logger.info(f"Agent channel registered for room {meetme_room}: {channel}")
        else:
            conversation_id = generate_conversation_id(meetme_room)
            room_state[meetme_room]["conversation_id"] = conversation_id
            room_state[meetme_room]["customer"] = {
                "channel": channel,
                "uniqueid": unique_id,
            }

            agent_data = room_state[meetme_room].get("agent", {})
            agent_channel = agent_data.get("channel")

            logger.info(
                f"FULL CONVERSATION CONNECTED | ConvID: {conversation_id} | "
                f"Room: {meetme_room} | Agent: {agent_channel} | Customer: {channel}"
            )

            # FIX: We snoop the AGENT channel for both roles, using 'in' and 'out' to separate legs.
            if agent_channel:
                # 1. Initialize session on StreamManager and retrieve active ports
                metadata = {
                    "meetme_room": meetme_room,
                    "agent_channel": agent_channel,
                    "customer_channel": channel,
                    "customer_caller_id": caller_id,
                }
                ports_info = init_stream_session(conversation_id, metadata)
                
                agent_port = ports_info.get("agent_port", 10000)
                customer_port = ports_info.get("customer_port", 10001)
                
                # Target Agent Voice
                start_external_media(
                    channel_id=agent_channel,
                    conversation_id=conversation_id,
                    role="agent",
                    port=agent_port,
                )
                
                # Target Customer Voice (Incoming to Agent Channel)
                start_external_media(
                    channel_id=agent_channel,
                    conversation_id=conversation_id,
                    role="customer",
                    port=customer_port,
                )
            else:
                logger.warning(f"Cannot start transcription for room {meetme_room}. Agent channel missing.")
                


def start_external_media(channel_id: str, conversation_id: str, role: str, port: int):
    ari_auth, ari_base_url = get_ari_config()
    stt_app_name = getattr(settings, "STT_APP_NAME")
    stt_server_ip = getattr(settings, "STT_SERVER_IP")
    
    try:
        encoded_channel_id = urllib.parse.quote_plus(channel_id)
        spy_direction = "in" if role.lower() == "agent" else "out"

        # 1. External Media Channel
        ext_res = requests.post(
            f"{ari_base_url}/channels/externalMedia",
            params={
                "app": stt_app_name,
                "external_host": f"{stt_server_ip}:{port}",
                "format": "ulaw",
                "transport": "udp",
                "encapsulation": "rtp",
                "connection_type": "client",
            },
            auth=ari_auth,
            timeout=2,
        )
        ext_res.raise_for_status()
        ext_id = ext_res.json().get("id")

        # 2. Snoop target channel
        snoop_res = requests.post(
            f"{ari_base_url}/channels/{encoded_channel_id}/snoop",
            params={
                "app": stt_app_name,
                "spy": spy_direction,
                "snoop_id": f"snoop_{role}_{conversation_id}",
            },
            auth=ari_auth,
            timeout=2,
        )
        snoop_res.raise_for_status()
        snoop_id = snoop_res.json().get("id")

        # 3. Create mixing bridge
        bridge_id = f"bridge_{role}_{conversation_id}"
        bridge_res = requests.post(
            f"{ari_base_url}/bridges",
            params={
                "app": stt_app_name,
                "type": "mixing",
                "bridgeId": bridge_id, # explicit ID naming makes cleanup easier
            },
            auth=ari_auth,
            timeout=2,
        )
        bridge_res.raise_for_status()

        # 4. Join Snoop and ExternalMedia to bridge
        requests.post(
            f"{ari_base_url}/bridges/{bridge_id}/addChannel",
            params={"channel": f"{snoop_id},{ext_id}"},
            auth=ari_auth,
            timeout=2,
        ).raise_for_status()

        logger.info(f"Started {role.upper()} audio stream on Port {port} for Conv: {conversation_id}")

    except Exception as e:
        logger.error(f"Failed to start External Media for {role} on channel {channel_id}: {str(e)}")


def process_meetme_leave(event):
    event_data = dict(event.keys) if hasattr(event, "keys") else event
    channel = event_data.get("Channel", "")
    meetme_room = event_data.get("Meetme", "")
    caller_id = event_data.get("CallerIDNum", "")

    if channel.startswith("Local/"):
        return
    
    if not meetme_room:
        return

    is_agent = caller_id == "0000000000"
    ari_auth, ari_base_url = get_ari_config()

    with room_lock:
        if meetme_room not in room_state:
            return

        room = room_state[meetme_room]
        conv_id = room.get("conversation_id")

        if is_agent:
            room.pop("agent", None)
            logger.info(f"Agent left room: {meetme_room}")
        else:
            room.pop("customer", None)
            logger.info(f"Customer left room: {meetme_room} | Ended ConvID: {conv_id}")

        # FIX: Active Asterisk resource teardown when the conversation falls apart
        if conv_id and ("agent" not in room or "customer" not in room):
            # Clean up Asterisk Snoop/ExternalMedia Bridges
            for role in ["agent", "customer"]:
                target_bridge = f"bridge_{role}_{conv_id}"
                try:
                    # Deleting the mixing bridge implicitly kicks out and destroys the snoop/externalMedia channels inside it
                    res = requests.delete(f"{ari_base_url}/bridges/{target_bridge}", auth=ari_auth, timeout=2)
                    if res.status_code == 204:
                        logger.info(f"Successfully cleaned up Asterisk bridge: {target_bridge}")
                except Exception as e:
                    logger.error(f"Error cleaning up bridge {target_bridge}: {str(e)}")
                    
            # Trigger StreamManager session closure (Stops sockets, merges PCM to stereo WAV, generates LLM summary)
            close_stream_session(conv_id)

        if "agent" not in room and "customer" not in room:
            room_state.pop(meetme_room, None)
            logger.info(f"Room {meetme_room} completely purged from state.")
