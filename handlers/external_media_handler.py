import threading
import time
import uuid
import urllib.parse
import requests
from services.logger_service import logger
from config.settings import settings

room_state = {}
room_lock = threading.Lock()


def generate_conversation_id(meetme_room: str) -> str:
    timestamp = int(time.time())
    short_hash = uuid.uuid4().hex[:6]
    return f"conv_{meetme_room}_{timestamp}_{short_hash}"


def process_meetme_join(event):
    event_data = dict(event.keys) if hasattr(event, "keys") else event

    channel = event_data.get("Channel", "")
    meetme_room = event_data.get("Meetme", "")
    caller_id = event_data.get("CallerIDNum", "")
    unique_id = event_data.get("Uniqueid", "")

    if not channel or not meetme_room:
        return

    is_agent = channel.startswith("Local/") or caller_id == "ding"

    with room_lock:
        if meetme_room not in room_state:
            room_state[meetme_room] = {}

        if is_agent:
            # Store Agent details
            room_state[meetme_room]["agent"] = {
                "channel": channel,
                "uniqueid": unique_id,
            }
            logger.info(f"Agent channel registered for room {meetme_room}: {channel}")

            # If customer was ALREADY waiting in the room, start agent stream now
            if (
                "customer" in room_state[meetme_room]
                and "conversation_id" in room_state[meetme_room]
            ):
                conv_id = room_state[meetme_room]["conversation_id"]
                start_external_media(
                    channel_id=channel,
                    conversation_id=conv_id,
                    role="agent",
                    port=10001,
                )
        else:
            # Customer joined logic
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

            # Trigger agent stream ONLY if agent channel is present
            if agent_channel:
                start_external_media(
                    channel_id=agent_channel,
                    conversation_id=conversation_id,
                    role="agent",
                    port=20000,
                )

            # Trigger customer stream
            start_external_media(
                channel_id=channel,
                conversation_id=conversation_id,
                role="customer",
                port=20002,
            )


def start_external_media(
    self, channel_id: str, conversation_id: str, role: str, target_port: int
) -> dict:
    """Snoops a specific channel and routes audio to a dedicated RTP port via ExternalMedia."""

    ari_host = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
    ari_user = getattr(settings, "ARI_USER", "stt_service")
    ari_password = getattr(settings, "ARI_PASS", "your_secure_ari_password")
    ari_auth = (ari_user, ari_password)
    ari_base_url = f"http://{ari_host}/ari"

    stt_app_name = getattr(settings, "STT_APP_NAME")
    stt_server_ip = getattr(settings, "STT_SERVER_IP")

    try:
        encoded_channel_id = urllib.parse.quote_plus(channel_id)

        # 1. External Media Channel
        ext_res = requests.post(
            f"{ari_base_url}/channels/externalMedia",
            params={
                "app": stt_app_name,
                "external_host": f"{stt_server_ip}:{target_port}",
                "format": "slin16",
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
                "spy": "in",
                "snoop_id": f"snoop_{role}_{conversation_id}",
            },
            auth=ari_auth,
            timeout=2,
        )
        snoop_res.raise_for_status()
        snoop_id = snoop_res.json().get("id")

        # 3. Create mixing bridge
        bridge_res = requests.post(
            f"{ari_base_url}/bridges",
            params={
                "app": stt_app_name,
                "type": "mixing",
                "name": f"bridge_{role}_{conversation_id}",
            },
            auth=ari_auth,
            timeout=2,
        )
        bridge_res.raise_for_status()
        bridge_id = bridge_res.json().get("id")

        # 4. Join Snoop and ExternalMedia to bridge
        requests.post(
            f"{ari_base_url}/bridges/{bridge_id}/addChannel",
            params={"channel": f"{snoop_id},{ext_id}"},
            auth=ari_auth,
            timeout=2,
        ).raise_for_status()

        logger.info(
            f"Started {role.upper()} audio stream for {conversation_id} on Port {target_port} (Channel: {channel_id})"
            f"external_media_id: {ext_id}"
            f"snoop_id: {snoop_id}"
            f"bridge_id: {bridge_id}"
        )

    except Exception as e:
        logger.error(f"Failed to start External Media for {channel_id}: {str(e)}")


def process_meetme_leave(event):
    event_data = dict(event.keys) if hasattr(event, "keys") else event
    channel = event_data.get("Channel", "")
    meetme_room = event_data.get("Meetme", "")
    caller_id = event_data.get("CallerIDNum", "")

    if not channel or not meetme_room:
        return

    is_agent = channel.startswith("Local/") or caller_id == "ding"

    # Reset room state when the customer leaves
    if not is_agent and meetme_room:
        with room_lock:
            removed_session = room_state.pop(meetme_room, None)
            if removed_session:
                conv_id = removed_session.get("conversation_id", "N/A")
                logger.info(
                    f"Customer Left Room: {meetme_room} | Ended ConvID: {conv_id}"
                )
