import requests
from services.logger_service import logger
from config.settings import settings
from services.vicidial_service import VicidialService


class CustomerService:
    def __init__(self):
        self.vicidial_service = VicidialService()
        self.vendor_webhook_url = settings.VENDOR_WEBHOOK_URL
        self.crm_webhook_url = settings.CRM_WEBHOOK_URL
        
        # Persistent HTTP Session for optimal performance
        self.http_session = requests.Session()
        
    
    def get_lead_info_from_vicidial(self, phone_number):
        logger.debug(f"Fetching lead info from Vicidial for phone: {phone_number}")
        
        try:
            lead_info = self.execute_one(
                """
                SELECT lead_id
                FROM vicidial_list
                WHERE phone_number = %s
                ORDER BY lead_id DESC
                LIMIT 1
                """,
                (phone_number,),
            )

            if not lead_info:
                logger.warning(f"No VICIdial lead found for {phone_number}")
                return None

            return lead_info
        except Exception as e:
            logger.error(f"Error fetching lead info from Vicidial for phone {phone_number}: {e}")
            return None
        
        
        
    
    def get_customer_info_from_vendor(self, phone):
        logger.debug(f"Calling Customer API for phone: {phone}")
        
        try: 
            response = self.http_session.post(
                self.vendor_webhook_url,
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
        except requests.RequestException as e:
            logger.error(f"Error calling Customer API for phone {phone}: {e}")
            return None
        
        
    

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
