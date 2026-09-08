import threading
import time
import websocket
import urllib.parse
import requests
from config.settings import settings
from services.logger_service import logger

ARI_HOST = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
ARI_USER = getattr(settings, "ARI_USER", "stt_service")
ARI_PASS = getattr(settings, "ARI_PASS", "your_secure_ari_password")
APP_NAME = "stt_service"
ARI_BASE_URL = f"http://{ARI_HOST}/ari"
ARI_AUTH = (ARI_USER, ARI_PASS)

def on_ws_open(ws):
    logger.info(f"ARI Stasis App '{APP_NAME}' successfully registered!")

def on_ws_error(ws, error):
    logger.error(f"ARI WebSocket Error: {error}")

def on_ws_close(ws, close_status_code, close_msg):
    logger.warning("ARI WebSocket Connection Closed. Reconnecting...")

def run_ari_websocket(*args, **kwargs):
    """Maintains an active WebSocket Stasis connection to register stt_service in Asterisk."""
    ws_url = f"ws://{ARI_HOST}/ari/events?api_key={ARI_USER}:{ARI_PASS}&app={APP_NAME}"
    
    while True:
        try:
            logger.info(f"Connecting ARI Stasis WebSocket for app '{APP_NAME}'...")
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_ws_open,
                on_error=on_ws_error,
                on_close=on_ws_close
            )
            ws.run_forever()
        except Exception:
            logger.exception("ARI WebSocket connection failed")
        
        time.sleep(3)

def start_ari_service():
    """Starts the ARI WebSocket in a daemon thread."""
    ari_thread = threading.Thread(target=run_ari_websocket, daemon=True, name="ari_stasis_ws")
    ari_thread.start()

def setup_single_channel_stream(channel_id, target_port, role, uniqueid, stt_server_ip="127.0.0.1"):
    """Snoops a specific channel and routes audio to a dedicated RTP port via ExternalMedia."""
    encoded_channel_id = urllib.parse.quote_plus(channel_id)

    # 1. External Media Channel
    ext_res = requests.post(
        f"{ARI_BASE_URL}/channels/externalMedia",
        params={
            "app": APP_NAME,
            "external_host": f"{stt_server_ip}:{target_port}",
            "format": "slin16"
        },
        auth=ARI_AUTH,
        timeout=2
    )
    ext_res.raise_for_status()
    ext_id = ext_res.json().get("id")

    # 2. Snoop target channel
    snoop_res = requests.post(
        f"{ARI_BASE_URL}/channels/{encoded_channel_id}/snoop",
        params={
            "app": APP_NAME,
            "spy": "in",
            "snoop_id": f"snoop_{role}_{uniqueid}"
        },
        auth=ARI_AUTH,
        timeout=2
    )
    snoop_res.raise_for_status()
    snoop_id = snoop_res.json().get("id")

    # 3. Create mixing bridge
    bridge_res = requests.post(
        f"{ARI_BASE_URL}/bridges",
        params={
            "app": APP_NAME,
            "type": "mixing",
            "name": f"bridge_{role}_{uniqueid}"
        },
        auth=ARI_AUTH,
        timeout=2
    )
    bridge_res.raise_for_status()
    bridge_id = bridge_res.json().get("id")

    # 4. Join Snoop and ExternalMedia to bridge
    requests.post(
        f"{ARI_BASE_URL}/bridges/{bridge_id}/addChannel",
        params={"channel": f"{snoop_id},{ext_id}"},
        auth=ARI_AUTH,
        timeout=2
    ).raise_for_status()

    logger.info(f"Started {role.upper()} audio stream for {uniqueid} on Port {target_port} (Channel: {channel_id})")