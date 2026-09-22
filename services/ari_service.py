import threading
import websocket

from config.settings import settings
from services.logger_service import logger


class ARIService:
    """Manages Asterisk REST Interface (ARI) WebSocket connections and media streaming setup."""

    def __init__(self):
        self.host = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
        self.user = getattr(settings, "ARI_USER", "stt_service")
        self.password = getattr(settings, "ARI_PASS", "your_secure_ari_password")

        self.app_name = getattr(settings, "STT_APP_NAME")
        self.ws_url = f"ws://{self.host}/ari/events?api_key={self.user}:{self.password}&app={self.app_name}"
        self.auth = (self.user, self.password)

        self._ws_thread = None
        self._ws = None
        self._stop_event = threading.Event()

    # WebSocket Event Callbacks
    def _on_ws_open(self, ws):
        logger.info(f"ARI Stasis App '{self.app_name}' successfully registered!")

    def _on_ws_error(self, ws, error):
        logger.error(f"ARI WebSocket Error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        logger.warning("ARI WebSocket Connection Closed.")

    # Connection & Service Handlers
    def _run_websocket(self):
        """Maintains an active WebSocket Stasis connection to register application in Asterisk."""
        while not self._stop_event.is_set():
            try:
                logger.info(
                    f"Connecting ARI Stasis WebSocket for app '{self.app_name}'..."
                )
                self._ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_ws_open,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                self._ws.run_forever()
            except Exception:
                logger.exception("ARI WebSocket connection failed")

            # Check for stop signal during reconnect sleep delay
            if self._stop_event.wait(timeout=3):
                break

    def start(self):
        """Starts the ARI WebSocket connection in a background daemon thread."""
        if self._ws_thread and self._ws_thread.is_alive():
            logger.warning("ARI Service thread is already running.")
            return

        self._stop_event.clear()
        self._ws_thread = threading.Thread(
            target=self._run_websocket, daemon=True, name="ari_stasis_ws"
        )
        self._ws_thread.start()

    def stop(self, timeout: float = 5.0):
        """Stops the ARI WebSocket connection and cleans up the background thread."""
        if not self._ws_thread or not self._ws_thread.is_alive():
            logger.warning("ARI Service is not running.")
            return

        logger.info("Stopping ARI Service...")
        self._stop_event.set()

        # Close active WebSocket connection to break out of run_forever()
        if self._ws:
            self._ws.close()

        # Join the thread to ensure complete shutdown
        self._ws_thread.join(timeout=timeout)
        if self._ws_thread.is_alive():
            logger.warning("ARI Service thread did not exit cleanly within timeout.")
        else:
            logger.info("ARI Service stopped successfully.")

        self._ws = None
        self._ws_thread = None