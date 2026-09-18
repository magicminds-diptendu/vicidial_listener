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
            # Store Agent details
            room_state[meetme_room]["agent"] = {
                "channel": channel,
                "uniqueid": unique_id
            }
            logger.info(f"Agent channel registered for room {meetme_room}: {channel}")

            # If customer was ALREADY waiting in the room, start agent stream now
            if "customer" in room_state[meetme_room] and "conversation_id" in room_state[meetme_room]:
                conv_id = room_state[meetme_room]["conversation_id"]
                start_external_media(
                    channel_id=channel,
                    conversation_id=conv_id,
                    role="agent",
                    port=10001
                )
        else:
            # Customer joined logic
            conversation_id = generate_conversation_id(meetme_room)
            room_state[meetme_room]["conversation_id"] = conversation_id
            room_state[meetme_room]["customer"] = {
                "channel": channel,
                "uniqueid": unique_id
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
                    port=10001
                )

            # Trigger customer stream
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

    if not channel or not meetme_room:
        return

    is_agent = channel.startswith("Local/") or caller_id == "ding"

    with room_lock:
        if meetme_room in room_state:
            if is_agent:
                # Agent logged off/left room completely
                room_state.pop(meetme_room, None)
                logger.info(f"Agent left room {meetme_room}. Cleaned up room state.")
            else:
                # Customer left - clear only customer and conversation_id
                room_state[meetme_room].pop("customer", None)
                old_conv = room_state[meetme_room].pop("conversation_id", None)
                logger.info(f"Customer left room {meetme_room}. Closed ConvID: {old_conv}")
                # Notice: room_state[meetme_room]["agent"] remains stored for the NEXT customer!