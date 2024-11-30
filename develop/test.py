import requests
import frappe

def create_user_in_external_system(doc, method):
    
    api_url = "https://office.enfono.com/api/resource/User"
    
    api_token = "1f99f5f4dc07b6a:258901802466295"
    
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": doc.name,          
        "first_name": doc.first_name,     
        "email": doc.email,          
    }
    
    frappe.logger().info(f"Sending payload to external system: {payload}")

    try:
        response = requests.get(f"{api_url}/{doc.email}", headers=headers)
        
        if response.status_code == 200:
            response = requests.put(f"{api_url}/{doc.email}", json=payload, headers=headers)
            if response.status_code in [200, 201]:
                frappe.msgprint(f"User {doc.username} updated successfully in external system.")
            else:
                frappe.throw(f"Failed to update user in external system: {response.text}")
        elif response.status_code == 404:
            response = requests.post(api_url, json=payload, headers=headers)
            if response.status_code in [200, 201]:
                frappe.msgprint(f"User {doc.username} created successfully in external system.")
            else:
                frappe.throw(f"Failed to create user in external system: {response.text}")
        else:
            frappe.throw(f"Failed to check user existence in external system: {response.text}")
        
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Error creating or updating user in external system: {str(e)}")



@frappe.whitelist(allow_guest=True)
def send_created_item_details(doc, method=None):
    try:
        frappe.logger().debug(f"Received doc: {doc.as_dict()}")

        item_details = {
            "code": doc.item_code,
            "name": doc.item_name,
            "rate": 0,
            "uom": doc.stock_uom,
            "sourceId": doc.name
        }

        frappe.logger().debug(f"Sending item details: {item_details}")

        mobile_app_url = "https://uat.industree.org.in/api/v1/production-item/create"

        response = requests.post(
            mobile_app_url,
            json=item_details,
            headers={"Content-Type": "application/json"}
        )

        frappe.logger().debug(f"Response Status Code: {response.status_code}")
        frappe.logger().debug(f"Response Content: {response.text}")

        if response.status_code == 200:
            frappe.logger().info(f"Item sent successfully to mobile app: {item_details}")
            frappe.msgprint(f"Item {doc.item_code} created successfully in the external system.")
        else:
            frappe.log_error(
                message=f"Failed to send item to mobile app. Response: {response.text}",
                title="Item Sync Error"
            )
            frappe.msgprint(f"Failed to send item {doc.item_code} to external system. Please try again.")

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            message=f"Network error while sending item to external system: {str(e)}",
            title="Item Sync Network Error"
        )
        frappe.msgprint(f"Network error: {str(e)}")

    except Exception as e:
        frappe.log_error(
            message=f"Unexpected error while sending item details: {str(e)}",
            title="Error in send_created_item_details"
        )
        frappe.msgprint(f"An unexpected error occurred: {str(e)}")
