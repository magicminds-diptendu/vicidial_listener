import time
import websocket
from collections import defaultdict
from threading import Event
from asterisk.ami import AMIClient
from config.settings import settings
from services.logger_service import logger

ARI_HOST = getattr(settings, "ARI_HOST", "127.0.0.1:8088")
ARI_USER = getattr(settings, "ARI_USER", "stt_service")
ARI_PASS = getattr(settings, "ARI_PASS", "your_secure_ari_password")
APP_NAME = "stt_service"

class AMIService:
    def __init__(self):
        self.client = None
        self._handlers = defaultdict(list)

    def connect(self):
        """Connect to Asterisk AMI and start listening."""
        self.client = AMIClient(
            address=settings.AMI_HOST,
            port=settings.AMI_PORT,
            timeout=None,
        )

        self.client.add_event_listener(self._dispatch)

        self.client.login(
            username=settings.AMI_USERNAME,
            secret=settings.AMI_PASSWORD,
        )

        logger.info(f"Connected to AMI ({settings.AMI_HOST}:{settings.AMI_PORT})")


    def disconnect(self):
        """Disconnect from AMI."""
        if self.client:
            try:
                self.client.logoff()
                logger.info("Disconnected from AMI")
            except Exception:
                pass

    def on(self, event_name: str):
        """
        Register an AMI event handler.

        Example:

            @ami.on("NewCallerid")
            def handle(event):
                ...
        """

        def decorator(func):
            self._handlers[event_name].append(func)
            logger.debug(f"Registered handler for '{event_name}'")
            return func

        return decorator

    def _dispatch(self, event, **kwargs):
        """Dispatch incoming AMI events."""

        logger.debug("=" * 50)
        logger.debug(event.name)
        logger.debug(event.keys)

        handlers = self._handlers.get(event.name, [])

        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(f"Error while handling event '{event.name}'")

    def start(self):
        """Start AMI listener."""

        self.connect()

        logger.info("AMI listener started")

        Event().wait()

    def run_ari_websocket():
        """Maintains an active WebSocket Stasis connection to register stt_service in Asterisk."""
        ws_url = f"ws://{ARI_HOST}/ari/events?api_key={ARI_USER}:{ARI_PASS}&app={APP_NAME}"
        
        while True:
            try:
                logger.info(f"Connecting ARI Stasis WebSocket for app '{APP_NAME}'...")
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=lambda ws: logger.info(f"ARI Stasis App '{APP_NAME}' successfully registered!"),
                    on_error=lambda ws, err: logger.error(f"ARI WebSocket Error: {err}"),
                    on_close=lambda ws, close_status, close_msg: logger.warning("ARI WebSocket Connection Closed. Reconnecting...")
                )
                ws.run_forever()
            except Exception:
                logger.exception("ARI WebSocket connection failed")
            
            time.sleep(3)  # Retry delay on connection loss
