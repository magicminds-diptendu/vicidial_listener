import requests
from config.settings import settings
from services.logger_service import logger
from services.vicidial_service import VicidialService

class LeadSyncService:

    def __init__(self):
        self.vicidial_service = VicidialService()
        self.vendor_webhook_url = settings.VENDOR_WEBHOOK_URL
        self.crm_webhook_url = settings.CRM_WEBHOOK_URL

        # Persistent HTTP Session for optimal performance
        self.http_session = requests.Session()

    def get_lead_info_from_vicidial(self, phone_number):
        logger.debug(
            f"Fetching lead info from Vicidial for phone: {phone_number}"
        )

        try:
            full_lead_info = self.vicidial_service.execute_one(
                """
                SELECT *
                FROM vicidial_list
                WHERE phone_number = %s
                ORDER BY lead_id DESC
                LIMIT 1
                """,
                (phone_number,),
            )

            if not full_lead_info:
                logger.warning(f"No VICIdial lead found for {phone_number}")
                return None

            return full_lead_info

        except Exception as e:
            logger.error(
                f"Error fetching lead info from Vicidial for phone {phone_number}: {e}"
            )
            return None

    def get_lead_info_from_vendor(self, phone):
        logger.debug(f"Calling Lead API for phone: {phone}")

        try:
            response = self.http_session.post(
                self.vendor_webhook_url,
                data={"phone": phone},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10,
            )

            if response.status_code != 200:
                logger.info(
                    f"API: No lead found for phone: {phone} (Status: {response.status_code})"
                )
                return None

            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error calling Lead API for phone {phone}: {e}")
            return None

    def send_lead_info_to_crm(self, lead_info):
        phone = lead_info.get("phone_number") or lead_info.get("phone")
        logger.debug(f"Calling CRM API for phone: {phone}")

        try:
            response = self.http_session.post(
                self.crm_webhook_url,
                json=lead_info,
                timeout=10,
            )

            if response.status_code != 200:
                logger.info(
                    f"API: CRM update non-200 response for phone: {phone} (Status: {response.status_code})"
                )
                return None

            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error calling CRM API for phone {phone}: {e}")
            return None

    def transform_payload_for_crm(self, lead_info, vendor_lead_info):
        phone = lead_info.get("phone_number")
        logger.debug(f"Transforming payload for CRM for phone: {phone}")

        vendor_data = vendor_lead_info or {}

        # Safely extract non-empty keys from vendor response
        vendor_fields = {
            k: v
            for k, v in vendor_data.items()
            if k in ("email", "bank_name") and v
        }

        # Merge payloads (vendor_fields overrides vicidial standard fields if set)
        return {**lead_info, **vendor_fields}

    def transform_lead_info_for_vicidial(self, crm_response):
        if not crm_response or not crm_response.get("success"):
            logger.error("Invalid or unsuccessful CRM response received.")
            return {}

        data = crm_response.get("data", {})
        contact = data.get("contact", {})

        if not contact:
            logger.warning("No contact information found in CRM response.")
            return {}

        return {
            "email": contact.get("email"),
            "alt_phone": contact.get("altPhone"),
            "first_name": contact.get("firstName"),
            "middle_initial": contact.get("middleInitial"),
            "last_name": contact.get("lastName"),
            "title": contact.get("title"),
            "gender": contact.get("gender"),
            "date_of_birth": contact.get("dateOfBirth"),
            "address1": contact.get("address1"),
            "address2": contact.get("address2"),
            "address3": contact.get("address3"),
            "city": contact.get("city"),
            "state": contact.get("state"),
            "province": contact.get("province"),
            "postal_code": contact.get("postalCode"),
            "country_code": contact.get("countryCode"),
            "comments": contact.get("comments"),
        }

    def transform_lead_info_for_custom(self, crm_response):
        if not crm_response or not crm_response.get("success"):
            logger.error("Invalid or unsuccessful CRM response received.")
            return {}

        data = crm_response.get("data", {})
        custom_fields = data.get("customFields", {})

        if not custom_fields:
            logger.warning("No custom fields found in CRM response.")
            return {}

        return {
            "bank_name": custom_fields.get("bank_name", ""),
            "no_of_family_members": custom_fields.get(
                "no_of_family_members", 0
            ),
            "no_of_computer_users": custom_fields.get(
                "no_of_computer_users", 0
            ),
            "bank_account_access_other_member": custom_fields.get(
                "bank_account_access_other_member", ""
            ),
        }

    def sync_vicidial_lead_info(self, phone):
        logger.debug(f"Syncing ViciDial lead info: {phone}")

        try:
            lead_info = self.get_lead_info_from_vicidial(phone)
            if not lead_info:
                logger.debug(
                    f"No lead info found in Vicidial for phone: {phone}"
                )
                return False

            vendor_lead_info = self.get_lead_info_from_vendor(phone)
            if not vendor_lead_info:
                logger.debug(
                    f"No lead info found in Vendor API for phone: {phone}"
                )

            transformed_payload = self.transform_payload_for_crm(
                lead_info, vendor_lead_info
            )
            crm_response = self.send_lead_info_to_crm(transformed_payload)
            if not crm_response:
                logger.debug(
                    f"Failed to sync lead info to CRM for phone: {phone}"
                )
                return False

            transformed_vicidial_payload = (
                self.transform_lead_info_for_vicidial(crm_response)
            )
            if not transformed_vicidial_payload:
                logger.debug(
                    f"Failed to transform CRM response for Vicidial update for phone: {phone}"
                )
                return False

            update_success = self.vicidial_service.update_list(
                lead_id=lead_info.get("lead_id"), **transformed_vicidial_payload
            )

            if not update_success:
                logger.debug(
                    f"Failed to update Vicidial lead info for phone: {phone}"
                )
                return False

            transformed_custom_payload = self.transform_lead_info_for_custom(
                crm_response
            )
            if not transformed_custom_payload:
                logger.debug(
                    f"Failed to transform CRM response for custom fields update for phone: {phone}"
                )
                return False

            update_custom_fields_success = (
                self.vicidial_service.update_custom_fields(
                    list_id=lead_info.get("list_id"),
                    lead_id=lead_info.get("lead_id"),
                    **transformed_custom_payload,
                )
            )

            if not update_custom_fields_success:
                logger.debug(
                    f"Failed to update Vicidial custom fields for phone: {phone}"
                )
                return False

            logger.info(
                f"Successfully synced lead info to CRM for phone: {phone}"
            )
            return True

        except requests.RequestException as e:
            logger.error(f"Error syncing vicidial for phone {phone}: {e}")
            return False
