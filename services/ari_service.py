import json
import threading
import time
import urllib.parse
import requests
import websocket

from config.settings import settings
from services.logger_service import logger


class ARIService:
    def __init__(self):
        self.ari_host = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
        self.ari_user = getattr(settings, "ARI_USER", "stt_service")
        self.ari_pass = getattr(settings, "ARI_PASS", "your_secure_ari_password")
        self.app_name = "stt_service"

        self.ari_base_url = f"http://{self.ari_host}/ari"
        self.ari_auth = (self.ari_user, self.ari_pass)
        self.stt_server_ip = getattr(settings, "STT_SERVER_IP", "127.0.0.1")
        
        # STT Webhook URLs
        self.stt_init_url = getattr(settings, "STT_INIT_URL", f"http://{self.stt_server_ip}:5000/session/init")
        self.stt_close_url = getattr(settings, "STT_CLOSE_URL", f"http://{self.stt_server_ip}:5000/session/close")
        
        self.udp_customer_port = getattr(settings, "UDP_CUSTOMER_PORT", 20000)
        self.udp_agent_port = getattr(settings, "UDP_AGENT_PORT", 20002)

        self.ws = None
        self.thread = None
        self.running = False

        # Persistent HTTP Session for optimal performance
        self.http_session = requests.Session()

        # Thread-safe Active Sessions Tracking
        self.active_sessions = set()
        self.sessions_lock = threading.Lock()

        # Memory mapping for ARI resource cleanup
        self.ari_resources = {}

    # -------------------------------------------------------------------------
    # STT Session Webhooks (Server 2)
    # -------------------------------------------------------------------------
    def initialize_stt_session(self, uniqueid, metadata, customer_ssrc=None, agent_ssrc=None):
        """Sends pre-setup metadata initialization payload to the external STT server."""
        with self.sessions_lock:
            if uniqueid not in self.active_sessions:
                self.active_sessions.add(uniqueid)
                
                init_payload = {
                    "uniqueid": uniqueid,
                    "metadata": metadata,
                    "customer_ssrc": customer_ssrc,
                    "agent_ssrc": agent_ssrc,
                    "customer_port": self.udp_customer_port,
                    "agent_port": self.udp_agent_port
                }

                try:
                    res = self.http_session.post(self.stt_init_url, json=init_payload, timeout=2)
                    res.raise_for_status()
                    logger.info(f"Initialized STT session on Server 2 for uniqueid: {uniqueid}")
                except Exception:
                    logger.exception(f"Failed to send /session/init payload to Server 2 for uniqueid: {uniqueid}")

    def close_stt_session(self, uniqueid):
        """Notifies Server 2 to close the STT session stream on call hangup."""
        try:
            res = self.http_session.post(self.stt_close_url, json={"uniqueid": uniqueid}, timeout=2)
            res.raise_for_status()
            logger.info(f"Closed STT session stream on Server 2 for UniqueID: {uniqueid}")
        except Exception:
            logger.exception(f"Failed to send /session/close payload to Server 2 for UniqueID: {uniqueid}")

    # -------------------------------------------------------------------------
    # WebSocket Event Handlers
    # -------------------------------------------------------------------------
    def _on_open(self, ws):
        logger.info(f"ARI Stasis App '{self.app_name}' successfully registered and connected!")

    def _on_error(self, ws, error):
        logger.error(f"ARI WebSocket Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"ARI WebSocket Closed (Code: {close_status_code}, Msg: {close_msg}). Reconnecting...")

    def _on_message(self, ws, message):
        """Processes real-time WebSocket events from Asterisk ARI."""
        try:
            event = json.loads(message)
            event_type = event.get("type")

            if event_type == "StasisStart":
                stasis_channel = event.get("channel", {})
                stasis_channel_id = stasis_channel.get("id")
                args = event.get("args", [])

                target_channel_id = args[0] if len(args) > 0 else stasis_channel_id
                lead_id = args[1] if len(args) > 1 and args[1] else "UNKNOWN"
                phone_number = args[2] if len(args) > 2 and args[2] else "UNKNOWN"

                uniqueid = f"{lead_id}_{stasis_channel_id}"

                logger.info(
                    f"StasisStart Triggered -> Channel: {stasis_channel_id} | "
                    f"Target: {target_channel_id} | Lead ID: {lead_id} | Phone: {phone_number}"
                )

                metadata = {
                    "lead_id": lead_id,
                    "phone_number": phone_number,
                    "target_channel": target_channel_id,
                    "stasis_channel": stasis_channel_id
                }

                # 1. Initialize STT Session on Server 2
                self.initialize_stt_session(
                    uniqueid=uniqueid,
                    metadata=metadata
                )

                self.ari_resources[stasis_channel_id] = {
                    "uniqueid": uniqueid,
                    "target_channel": target_channel_id,
                    "bridges": [],
                    "channels": []
                }

                # 2. Setup Dual Channel Stream (Customer & Agent RTP Ports)
                self.setup_dual_channel_stream(
                    stasis_channel_id=stasis_channel_id,
                    target_channel_id=target_channel_id,
                    uniqueid=uniqueid,
                    lead_id=lead_id
                )

            elif event_type == "StasisEnd":
                stasis_channel_id = event.get("channel", {}).get("id")
                logger.info(f"StasisEnd Event Received -> Channel: {stasis_channel_id}. Initiating teardown...")
                
                # Cleanup ARI resources and send /session/close webhook
                self.cleanup_channel_resources(stasis_channel_id)

        except Exception:
            logger.exception("Error processing ARI WebSocket message")

    # -------------------------------------------------------------------------
    # ARI Audio Streaming Setup
    # -------------------------------------------------------------------------
    def setup_dual_channel_stream(self, stasis_channel_id, target_channel_id, uniqueid, lead_id):
        """Snoops customer and agent directions and streams them to remote UDP ports."""
        encoded_target_id = urllib.parse.quote_plus(target_channel_id)
        resource_tracker = self.ari_resources.get(stasis_channel_id)

        streams = [
            {"role": "customer", "spy": "in", "port": self.udp_customer_port},
            {"role": "agent", "spy": "out", "port": self.udp_agent_port}
        ]

        for stream in streams:
            role = stream["role"]
            port = stream["port"]
            spy_direction = stream["spy"]

            try:
                # 1. External Media Channel Creation
                ext_res = self.http_session.post(
                    f"{self.ari_base_url}/channels/externalMedia",
                    params={
                        "app": self.app_name,
                        "external_host": f"{self.stt_server_ip}:{port}",
                        "format": "slin16"
                    },
                    auth=self.ari_auth,
                    timeout=2
                )
                ext_res.raise_for_status()
                ext_id = ext_res.json().get("id")

                # 2. Snoop target channel direction
                snoop_res = self.http_session.post(
                    f"{self.ari_base_url}/channels/{encoded_target_id}/snoop",
                    params={
                        "app": self.app_name,
                        "spy": spy_direction,
                        "snoop_id": f"snoop_{role}_{uniqueid}"
                    },
                    auth=self.ari_auth,
                    timeout=2
                )
                snoop_res.raise_for_status()
                snoop_id = snoop_res.json().get("id")

                # 3. Create mixing bridge
                bridge_res = self.http_session.post(
                    f"{self.ari_base_url}/bridges",
                    params={
                        "app": self.app_name,
                        "type": "mixing",
                        "name": f"bridge_{role}_{uniqueid}"
                    },
                    auth=self.ari_auth,
                    timeout=2
                )
                bridge_res.raise_for_status()
                bridge_id = bridge_res.json().get("id")

                # 4. Join Snoop and ExternalMedia channels to the bridge
                self.http_session.post(
                    f"{self.ari_base_url}/bridges/{bridge_id}/addChannel",
                    params={"channel": f"{snoop_id},{ext_id}"},
                    auth=self.ari_auth,
                    timeout=2
                ).raise_for_status()

                if resource_tracker:
                    resource_tracker["bridges"].append(bridge_id)
                    resource_tracker["channels"].extend([ext_id, snoop_id])

                logger.info(
                    f"Streaming {role.upper()} audio to {self.stt_server_ip}:{port} | UniqueID: {uniqueid}"
                )

            except Exception:
                logger.exception(f"Failed to set up {role.upper()} stream on Port {port} for UniqueID: {uniqueid}")

    # -------------------------------------------------------------------------
    # Resource Teardown & STT Close Webhook
    # -------------------------------------------------------------------------
    def cleanup_channel_resources(self, stasis_channel_id):
        """Cleans up ARI resources and sends /session/close on StasisEnd."""
        tracker = self.ari_resources.pop(stasis_channel_id, None)
        if not tracker:
            logger.warning(f"No active resource tracker found for cleanup on Channel: {stasis_channel_id}")
            return

        uniqueid = tracker.get("uniqueid")

        # 1. Destroy mixing bridges
        for bridge_id in tracker.get("bridges", []):
            try:
                self.http_session.delete(
                    f"{self.ari_base_url}/bridges/{bridge_id}",
                    auth=self.ari_auth,
                    timeout=2
                )
                logger.info(f"Destroyed mixing bridge: {bridge_id}")
            except Exception:
                logger.exception(f"Error destroying bridge: {bridge_id}")

        # 2. Destroy snoop and external media channels
        for channel_id in tracker.get("channels", []):
            try:
                self.http_session.delete(
                    f"{self.ari_base_url}/channels/{channel_id}",
                    auth=self.ari_auth,
                    timeout=2
                )
                logger.info(f"Closed channel: {channel_id}")
            except Exception:
                logger.exception(f"Error hanging up channel: {channel_id}")

        # 3. Send /session/close to Server 2
        self.close_stt_session(uniqueid)

        # 4. Remove session tracking record
        with self.sessions_lock:
            self.active_sessions.discard(uniqueid)

        logger.info(f"Completed full resource cleanup and session closure for UniqueID: {uniqueid}")

    # -------------------------------------------------------------------------
    # Thread Lifecycle Management
    # -------------------------------------------------------------------------
    def _run_websocket(self):
        ws_url = (
            f"ws://{self.ari_host}/ari/events"
            f"?api_key={self.ari_user}:{self.ari_pass}&app={self.app_name}"
        )

        while self.running:
            try:
                logger.info(f"Connecting ARI Stasis WebSocket for app '{self.app_name}'...")
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.run_forever()
            except Exception:
                logger.exception("ARI WebSocket connection failed")

            time.sleep(3)

    def start(self):
        """Starts the ARI service background daemon thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(
                target=self._run_websocket,
                daemon=True,
                name="ari_stasis_ws"
            )
            self.thread.start()
            logger.info("ARI Service thread started successfully.")

    def stop(self):
        """Stops the ARI service thread."""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("ARI Service thread stopped.")