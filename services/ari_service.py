import threading
import time
import urllib.parse
import requests
import websocket

from config.settings import settings
from services.logger_service import logger


class ARIService:
    """Manages Asterisk REST Interface (ARI) WebSocket connections and media streaming setup."""

    def __init__(self, app_name="stt_service"):
        self.host = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
        self.user = getattr(settings, "ARI_USER", "stt_service")
        self.password = getattr(settings, "ARI_PASS", "your_secure_ari_password")
        self.app_name = app_name

        self.base_url = f"http://{self.host}/ari"
        self.ws_url = f"ws://{self.host}/ari/events?api_key={self.user}:{self.password}&app={self.app_name}"
        self.auth = (self.user, self.password)

        self._ws_thread = None
        self._ws = None
        

    # WebSocket Event Callbacks
    def _on_ws_open(self, ws):
        logger.info(f"ARI Stasis App '{self.app_name}' successfully registered!")

    def _on_ws_error(self, ws, error):
        logger.error(f"ARI WebSocket Error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        logger.warning("ARI WebSocket Connection Closed. Reconnecting...")

    # Connection & Service Handlers
    def _run_websocket(self):
        """Maintains an active WebSocket Stasis connection to register application in Asterisk."""
        while True:
            try:
                logger.info(f"Connecting ARI Stasis WebSocket for app '{self.app_name}'...")
                self._ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_ws_open,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                self._ws.run_forever()
            except Exception:
                logger.exception("ARI WebSocket connection failed")

            time.sleep(3)

    def start(self):
        """Starts the ARI WebSocket connection in a background daemon thread."""
        if self._ws_thread and self._ws_thread.is_alive():
            logger.warning("ARI Service thread is already running.")
            return

        self._ws_thread = threading.Thread(
            target=self._run_websocket, 
            daemon=True, 
            name="ari_stasis_ws"
        )
        self._ws_thread.start()

    # Media Streaming Operations
    def setup_single_channel_stream(
        self, 
        channel_id: str, 
        target_port: int, 
        role: str, 
        uniqueid: str, 
        stt_server_ip: str = "127.0.0.1"
    ) -> dict:
        """Snoops a specific channel and routes audio to a dedicated RTP port via ExternalMedia."""
        encoded_channel_id = urllib.parse.quote_plus(channel_id)

        # 1. External Media Channel
        ext_res = requests.post(
            f"{self.base_url}/channels/externalMedia",
            params={
                "app": self.app_name,
                "external_host": f"{stt_server_ip}:{target_port}",
                "format": "slin16",
            },
            auth=self.auth,
            timeout=2,
        )
        ext_res.raise_for_status()
        ext_id = ext_res.json().get("id")

        # 2. Snoop target channel
        snoop_res = requests.post(
            f"{self.base_url}/channels/{encoded_channel_id}/snoop",
            params={
                "app": self.app_name,
                "spy": "in",
                "snoop_id": f"snoop_{role}_{uniqueid}",
            },
            auth=self.auth,
            timeout=2,
        )
        snoop_res.raise_for_status()
        snoop_id = snoop_res.json().get("id")

        # 3. Create mixing bridge
        bridge_res = requests.post(
            f"{self.base_url}/bridges",
            params={
                "app": self.app_name,
                "type": "mixing",
                "name": f"bridge_{role}_{uniqueid}",
            },
            auth=self.auth,
            timeout=2,
        )
        bridge_res.raise_for_status()
        bridge_id = bridge_res.json().get("id")

        # 4. Join Snoop and ExternalMedia to bridge
        requests.post(
            f"{self.base_url}/bridges/{bridge_id}/addChannel",
            params={"channel": f"{snoop_id},{ext_id}"},
            auth=self.auth,
            timeout=2,
        ).raise_for_status()

        logger.info(
            f"Started {role.upper()} audio stream for {uniqueid} on Port {target_port} (Channel: {channel_id})"
        )

        return {
            "external_media_id": ext_id,
            "snoop_id": snoop_id,
            "bridge_id": bridge_id,
        }