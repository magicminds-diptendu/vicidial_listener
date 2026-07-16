from collections import defaultdict
from threading import Event
from asterisk.ami import AMIClient
from config.settings import settings
from services.logger import logger


class AMIService:
    def __init__(self):
        self.client = None
        self._handlers = defaultdict(list)

    def connect(self):
        """Connect to Asterisk AMI."""
        self.client = AMIClient(
            address=settings.AMI_HOST,
            port=settings.AMI_PORT,
        )

        self.client.login(
            username=settings.AMI_USERNAME,
            secret=settings.AMI_PASSWORD,
        )

        self.client.add_event_listener(self._dispatch)

        logger.info(f"Connected to AMI ({settings.AMI_HOST}:{settings.AMI_PORT})")

    def disconnect(self):
        if self.client:
            self.client.logoff()
            logger.info("Disconnected from AMI")

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
        handlers = self._handlers.get(event.name, [])

        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(f"Error while handling event '{event.name}'")

    def start(self):
        self.connect()

        logger.info("AMI listener started")

        Event().wait()
