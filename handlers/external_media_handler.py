import threading
from services.logger_service import logger

room_state = {}
room_lock = threading.Lock()


def handle_external_media_stream(event):
    channel = event.get("Channel", "")
    meetme_room = event.get("Meetme", "")
    caller_id = event.get("CallerIDNum", "")
    unique_id = event.get("Uniqueid", "")

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
        else:
            # Customer joined: combine both channel details
            room_state[meetme_room]["customer"] = {
                "channel": channel,
                "uniqueid": unique_id
            }
            
            agent_data = room_state[meetme_room].get("agent")
            customer_data = room_state[meetme_room]["customer"]

            logger.info(
                f"FULL CONVERSATION CONNECTED | Room: {meetme_room} | "
                f"Agent Channel: {agent_data.get('channel') if agent_data else 'N/A'} | "
                f"Customer Channel: {customer_data['channel']}"
            )