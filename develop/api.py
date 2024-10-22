import frappe
import requests
import json

@frappe.whitelist(allow_guest=True)  
def fetch_and_post_sensor_data():
    sensor_api_url = "https://dfwsa.deepflow.in/api/data/list/"
    
    try:
        response = requests.get(sensor_api_url)
        response.raise_for_status()
        data = response.json()
        frappe.msgprint("Sensor data fetched successfully")
        print("Sensor data fetched successfully:", data)
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Failed to fetch sensor data. Error: {e}")
        return

    if isinstance(data, list):
        for sensor in data:
            try:
                deviceid = sensor.get("device")
                
                existing_sensor_data = frappe.get_all("Sensor Data", filters={"deviceid": deviceid})
                
                if existing_sensor_data:
                    frappe.msgprint(f"Sensor data for Device ID: {deviceid} already exists. Skipping...")
                    print(f"Sensor data for Device ID: {deviceid} already exists. Skipping...")
                    continue 
                
                sensor_payload = {
                    "deviceid": deviceid,
                    "temperature": sensor.get("temperature"),
                    "pressure": sensor.get("pressure"),
                    "lux": sensor.get("lux"),
                    "direction": sensor.get("direction"),
                    "angle": sensor.get("angle"),
                    "speed": sensor.get("speed"),
                    "speed_max": sensor.get("speed_max"),
                    "rainfall": sensor.get("rainfall"),
                    "rainfall_24": sensor.get("rainfall_24"),
                    "humidity": sensor.get("humidity")
                }

                sensor_data_doc = frappe.get_doc({
                    "doctype": "Sensor Data",
                    "table_bblg": [sensor_payload]  
                })
                
                sensor_data_doc.insert()

                frappe_response = requests.post(
                    "https://weatherwise.frappe.cloud/api/resource/Sensor%20Data",
                    headers={
                        "Authorization": "Token f14b06aeaa3949b:3db029195ed5cef",
                        "Content-Type": "application/json"
                    },
                    data=json.dumps({"table_bblg": [sensor_payload]})
                )
                frappe_response.raise_for_status()  
                
                frappe.msgprint(f"Sensor data created successfully for Device ID: {deviceid}")
                print(f"Sensor data created successfully for Device ID: {deviceid}")

            except requests.exceptions.RequestException as e:
                frappe.log_error(message=f"Error posting sensor data for Device ID: {deviceid}. Error: {e}")
                frappe.msgprint(f"Error posting sensor data for Device ID: {deviceid}. Error: {e}")
            except Exception as e:
                frappe.log_error(message=f"Error creating sensor data for Device ID: {deviceid}. Error: {e}")
                frappe.msgprint(f"Error creating sensor data for Device ID: {deviceid}. Error: {e}")

    else:
        frappe.throw("Unexpected response format")
        print("Unexpected response format:", data)

    print("Sensor data processing completed.")
    frappe.msgprint("Sensor data processing completed.")




# import frappe
# import json


# @frappe.whitelist()
# def add_item():
#     data = json.loads(frappe.request.data)
    
#     item_doc = frappe.get_doc({
#             "doctype": "Item",
#             "item_code": data.get("item_code"),
#             "item_name": data.get("item_name"),
#             "item_group": data.get("item_group")
#         })

#     item_doc.insert()

# @frappe.whitelist()
# def add_customer():
#     data = json.loads(frappe.request.data)
    
#     new_cus = frappe.get_doc({
#             "doctype": "Customer",
#             "customer_name": data.get("customer_name"),
#         })

#     new_cus.insert()

# @frappe.whitelist()
# def add_sales_invoice():
#     data = json.loads(frappe.request.data)

#     sales_invoice_doc = frappe.get_doc({
#         "doctype": "Sales Invoice",
#         "customer": data.get("customer"),
#         "posting_date": data.get("posting_date"),
#         "items": data.get("items"), 
#     })


#     sales_invoice_doc.insert()
#     sales_invoice_doc.submit()  