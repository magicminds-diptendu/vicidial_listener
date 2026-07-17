import requests
from services.logger import logger
from config.settings import settings


class CustomerService:

    def get_customer(self, phone):
        logger.debug(f"Calling Customer API for phone: {phone}")

        url = settings.API_BASE_URL

        response = requests.post(
            url,
            data={"phone": phone},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )

        logger.debug(f"Customer API Status: {response.status_code}")

        if response.status_code != 200:
            logger.info(f"API: No customer found for phone: {phone}")
            return None

        return response.json()
