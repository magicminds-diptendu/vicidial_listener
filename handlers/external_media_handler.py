import threading
import time
import uuid
from services.logger_service import logger

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
            room_state[meetme_room]["agent"] = {
                "channel": channel,
                "uniqueid": unique_id
            }
        else:
            # 1. Generate unique conversation ID for this call session
            conversation_id = generate_conversation_id(meetme_room)

            # 2. Store customer data and conversation ID
            room_state[meetme_room]["conversation_id"] = conversation_id
            room_state[meetme_room]["customer"] = {
                "channel": channel,
                "uniqueid": unique_id
            }

            agent_data = room_state[meetme_room].get("agent", {})
            customer_data = room_state[meetme_room]["customer"]
            agent_channel = agent_data.get("channel")

            logger.info(
                f"FULL CONVERSATION CONNECTED | ConvID: {conversation_id} | "
                f"Room: {meetme_room} | Agent: {agent_channel} | Customer: {channel}"
            )

            # 3. Trigger External Media Streams for both channels
            if agent_channel:
                start_external_media(
                    channel_id=agent_channel,
                    conversation_id=conversation_id,
                    role="agent",
                    port=10001
                )

            start_external_media(
                channel_id=channel,
                conversation_id=conversation_id,
                role="customer",
                port=10002
            )

def start_external_media(channel_id: str, conversation_id: str, role: str, port: int):
    """
    Executes ARI ExternalMedia creation for a specific channel leg.
    """
    try:
        # Example ARI ExternalMedia invocation
        # ari.channels.externalMedia(
        #     channelId=channel_id,
        #     app="vicidial_audio_app",
        #     external_host=f"127.0.0.1:{port}",
        #     format="slin16",
        #     transport="udp",
        #     direction="both",
        #     variables={"CONVERSATION_ID": conversation_id, "ROLE": role}
        # )
        logger.info(f"External Media Started | Channel: {channel_id} | Role: {role} | ConvID: {conversation_id} | Port: {port}")
    except Exception as e:
        logger.error(f"Failed to start External Media for {channel_id}: {str(e)}")
        
        

def process_meetme_leave(event):
    event_data = dict(event.keys) if hasattr(event, "keys") else event
    channel = event_data.get("Channel", "")
    meetme_room = event_data.get("Meetme", "")
    caller_id = event_data.get("CallerIDNum", "")

    is_agent = channel.startswith("Local/") or caller_id == "ding"

    # Reset room state when the customer leaves
    if not is_agent and meetme_room:
        with room_lock:
            removed_session = room_state.pop(meetme_room, None)
            if removed_session:
                conv_id = removed_session.get("conversation_id", "N/A")
                logger.info(f"Customer Left Room: {meetme_room} | Ended ConvID: {conv_id}")