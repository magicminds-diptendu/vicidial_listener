import requests
from services.logger import logger
from config.settings import settings


class CustomerService:

    def get_customer(self, params):
        logger.info("Calling Customer API")

        url = settings.API_BASE_URL

        response = requests.post(
            url,
            json=params,
            headers={
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        logger.info(f"Customer API Status: {response.status_code}")

        response.raise_for_status()

        return response.json()
