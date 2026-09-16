import json
import requests
from config.settings import settings


def send_lead_info_to_crm(lead_info):
    crm_webhook_url = settings.CRM_WEBHOOK_URL
    phone = lead_info.get("phone_number") or lead_info.get("phone")

    print(f"[DEBUG] Starting send_lead_info_to_crm for phone: {phone}")
    print(f"[DEBUG] Target URL: {crm_webhook_url}")

    try:
        payload = json.loads(json.dumps(lead_info, default=str))
        print(f"[DEBUG] Payload generated successfully: {payload}")

        print("[DEBUG] Sending POST request...")
        response = requests.post(
            crm_webhook_url,
            json=payload,
            timeout=10,
        )

        print(f"[INFO] HTTP Status Code: {response.status_code}")
        response.raise_for_status()

        response_data = response.json()
        return response_data

    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] CRM API returned error status ({response.status_code}): {e}")
        return None
    except requests.exceptions.JSONDecodeError:
        print(f"[ERROR] CRM API response was not valid JSON: {response.text}")
        return None
    except requests.RequestException as e:
        print(f"[ERROR] Request failed completely: {e}")
        return None


if __name__ == "__main__":
    lead_info = {
        "click_source": "vicidial",
        "lead_id": 21,
        "entry_date": "2026-09-16 07:32:03",
        "modify_date": "2026-09-16 07:32:03",
        "status": "INBND",
        "user": "12032788053",
        "vendor_lead_code": "12032788053",
        "source_id": "VDCL",
        "list_id": 999,
        "gmt_offset_now": "-4.00",
        "called_since_last_reset": "Y",
        "phone_code": "1",
        "phone_number": "6149542636",
        "title": None,
        "first_name": None,
        "middle_initial": None,
        "last_name": None,
        "address1": None,
        "address2": None,
        "address3": None,
        "city": None,
        "state": None,
        "province": None,
        "postal_code": None,
        "country_code": None,
        "gender": "U",
        "date_of_birth": None,
        "alt_phone": None,
        "email": None,
        "security_phrase": "TollFreee",
        "comments": "16149542636",
        "called_count": 1,
        "last_local_call_time": None,
        "rank": 0,
        "owner": "",
        "entry_list_id": 0,
    }

    print("--- STARTING SCRIPT TEST ---")
    result = send_lead_info_to_crm(lead_info)
    print(f"--- SCRIPT FINISHED | Final Return Value: {result} ---")