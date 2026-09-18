import threading
from services.logger_service import logger

# Thread-safe conversation state tracker
# Structure: { "8600052": { "conversation_id": "...", "customer_channel": "...", "lead_id": "..." } }
room_tracker = {}
tracker_lock = threading.Lock()


def extract_lead_id_from_callerid(caller_id_name: str) -> str:
    """Extracts Vicidial Lead ID from CallerIDName format like 'Y9180925460000000040'."""
    if caller_id_name and caller_id_name.startswith("Y"):
        return str(int(caller_id_name[-10:]))  # Extracts '40'
    return ""


def meetme_join_handler(event):
    channel = event.get("Channel", "")
    meetme_room = event.get("Meetme", "")
    caller_id_num = event.get("CallerIDNum", "")
    caller_id_name = event.get("CallerIDName", "")
    unique_id = event.get("Uniqueid", "")
    user_id = event.get("User", "")

    if not channel or not meetme_room:
        return

    # 1. Filter out temporary local setup legs (e.g., Local/...;2 with CallerID 'ding')
    is_setup_leg = channel.startswith("Local/") or caller_id_num == "ding"
    if is_setup_leg:
        logger.debug(f"Ignoring setup leg: {channel} in room {meetme_room}")
        return

    # 2. Customer Channel Joined (e.g., SIP/ATnT-00000033)
    lead_id = extract_lead_id_from_callerid(caller_id_name)
    conversation_id = f"conv_{meetme_room}_{unique_id}"

    with tracker_lock:
        room_tracker[meetme_room] = {
            "conversation_id": conversation_id,
            "customer_channel": channel,
            "customer_phone": caller_id_num,
            "lead_id": lead_id,
            "unique_id": unique_id,
            "agent_user_id": user_id
        }

    logger.info(
        f"FULL CONVERSATION CONNECTED | ConvID: {conversation_id} | "
        f"Room: {meetme_room} | Customer Channel: {channel} | "
        f"Phone: {caller_id_num} | Lead ID: {lead_id}"
    )

    # Trigger audio streaming / CRM sync with aggregated context
    # start_external_audio_stream(conversation_id, channel, meetme_room)


def meetme_leave_handler(event):
    channel = event.get("Channel", "")
    meetme_room = event.get("Meetme", "")

    # Clean state when customer leaves room
    if not channel.startswith("Local/"):
        with tracker_lock:
            session = room_tracker.pop(meetme_room, None)
            if session:
                logger.info(
                    f"CONVERSATION ENDED | ConvID: {session['conversation_id']} | "
                    f"Room: {meetme_room} cleared."
                )