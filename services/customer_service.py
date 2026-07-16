import requests

from config.settings import settings


class CustomerService:

    def get_customer(self, phone):

        url = f"{settings.API_BASE_URL}/customer/lookup"

        response = requests.post(
            url,
            json={"phone": phone},
            headers={"Authorization": f"Bearer {settings.API_TOKEN}"},
            timeout=10,
        )

        return response.json()
