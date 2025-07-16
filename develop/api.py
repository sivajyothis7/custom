# import frappe
# import requests
# import json

# @frappe.whitelist(allow_guest=True)  
# def fetch_and_post_sensor_data():
#     sensor_api_url = "https://dfwsa.deepflow.in/api/data/list/"
    
#     try:
#         response = requests.get(sensor_api_url)
#         response.raise_for_status()
#         data = response.json()
#         frappe.msgprint("Sensor data fetched successfully")
#         print("Sensor data fetched successfully:", data)
#     except requests.exceptions.RequestException as e:
#         frappe.throw(f"Failed to fetch sensor data. Error: {e}")
#         return

#     if isinstance(data, list):
#         for sensor in data:
#             try:
#                 deviceid = sensor.get("device")
                
#                 existing_sensor_data = frappe.get_all("Sensor Data", filters={"deviceid": deviceid})
                
#                 if existing_sensor_data:
#                     frappe.msgprint(f"Sensor data for Device ID: {deviceid} already exists. Skipping...")
#                     print(f"Sensor data for Device ID: {deviceid} already exists. Skipping...")
#                     continue 
                
#                 sensor_payload = {
#                     "deviceid": deviceid,
#                     "temperature": sensor.get("temperature"),
#                     "pressure": sensor.get("pressure"),
#                     "lux": sensor.get("lux"),
#                     "direction": sensor.get("direction"),
#                     "angle": sensor.get("angle"),
#                     "speed": sensor.get("speed"),
#                     "speed_max": sensor.get("speed_max"),
#                     "rainfall": sensor.get("rainfall"),
#                     "rainfall_24": sensor.get("rainfall_24"),
#                     "humidity": sensor.get("humidity")
#                 }

#                 sensor_data_doc = frappe.get_doc({
#                     "doctype": "Sensor Data",
#                     "table_bblg": [sensor_payload]  
#                 })
                
#                 sensor_data_doc.insert()

#                 frappe_response = requests.post(
#                     "https://weatherwise.frappe.cloud/api/resource/Sensor%20Data",
#                     headers={
#                         "Authorization": "Token f14b06aeaa3949b:3db029195ed5cef",
#                         "Content-Type": "application/json"
#                     },
#                     data=json.dumps({"table_bblg": [sensor_payload]})
#                 )
#                 frappe_response.raise_for_status()  
                
#                 frappe.msgprint(f"Sensor data created successfully for Device ID: {deviceid}")
#                 print(f"Sensor data created successfully for Device ID: {deviceid}")

#             except requests.exceptions.RequestException as e:
#                 frappe.log_error(message=f"Error posting sensor data for Device ID: {deviceid}. Error: {e}")
#                 frappe.msgprint(f"Error posting sensor data for Device ID: {deviceid}. Error: {e}")
#             except Exception as e:
#                 frappe.log_error(message=f"Error creating sensor data for Device ID: {deviceid}. Error: {e}")
#                 frappe.msgprint(f"Error creating sensor data for Device ID: {deviceid}. Error: {e}")

#     else:
#         frappe.throw("Unexpected response format")
#         print("Unexpected response format:", data)

#     print("Sensor data processing completed.")
#     frappe.msgprint("Sensor data processing completed.")

# import frappe
# import requests
# import json

# @frappe.whitelist(allow_guest=True)
# def sync_customers_from_external_api():
#     external_api_url = "https://dev-api.basket4me.com:8443/api/businesserp/customers"
#     external_api_headers = {
#         "x-access-apikey": "X355D9FAC5E211EF80AB0A46B22E7688"
#     }
#     external_api_params = {
#         "storeCode": "BRUAE101S00101",
#         "accessDate": "2024-12-29",
#         "page": 1
#     }

#     try:
#         response = requests.get(external_api_url, headers=external_api_headers, params=external_api_params)
#         response.raise_for_status()
#         data = response.json()

#         if not data or "data" not in data:
#             frappe.log_error("No data received from external API", "Sync Customers")
#             return

#         for customer in data["data"]:
#             store_name = customer.get("storeName")

#             if not store_name:
#                 frappe.log_error("Missing 'storeName' in customer data", "Sync Customers")
#                 continue

#             existing_customer = frappe.db.get_value(
#                 "Customer", {"customer_name": store_name}, ["name"], as_dict=True
#             )

#             customer_payload = {
#                 "customer_name": store_name,
#                 "custom_store_mobile": customer.get("storeMobile"),
#                 "custom_district": customer.get("storeDistrictName"),
#                 "custom_custom_location": customer.get("storeLocationName"),
#                 "custom_state": customer.get("storeStateName"),
#                 "custom_pin_code": customer.get("storePinCode"),
#                 "custom_name_of_contact_person": customer.get("storeContactPerson")
#             }

#             if existing_customer:
#                 customer_doc = frappe.get_doc("Customer", existing_customer["name"])
#                 changes_made = False

#                 for key, value in customer_payload.items():
#                     if customer_doc.get(key) != value:
#                         customer_doc.set(key, value)
#                         changes_made = True

#                 if changes_made:
#                     customer_doc.save(ignore_permissions=True)
#                     frappe.db.commit()
#             else:
#                 customer_doc = frappe.get_doc({
#                     "doctype": "Customer",
#                     **customer_payload
#                 })
#                 customer_doc.insert(ignore_permissions=True)
#                 frappe.db.commit()

#     except requests.exceptions.RequestException as e:
#         frappe.log_error(f"Failed to fetch data: {e}", "Sync Customers")
#     except Exception as e:
#         frappe.log_error(f"Error syncing customers: {e}", "Sync Customers")




# @frappe.whitelist(allow_guest=True)
# def sync_sales_orders_from_external_api():
#     external_api_url = "https://dev-api.basket4me.com:8443/api/businesserp/salesOrders"
#     external_api_headers = {
#         "x-access-apikey": "X355D9FAC5E211EF80AB0A46B22E7688"
#     }
#     external_api_params = {
#         "storeCode": "BRUAE101S00101",
#         "accessDate": "2024-12-29",
#         "page": 1
#     }

#     erpnext_api_url = "http://127.0.0.1:8004/api/resource/Sales Order"

#     erpnext_headers = {
#         "Authorization": "token 36ea8b8aeafc018:c431df641cb95d7",
#         "Content-Type": "application/json"
#     }

#     try:
#         response = requests.get(external_api_url, headers=external_api_headers, params=external_api_params)
#         response.raise_for_status()
#         data = response.json()

#         if not data or "data" not in data:
#             frappe.log_error("No data received from external API", "Sync Sales Orders")
#             return

#         for order in data["data"]:
#             customer_name = order.get("customer_name", "abc")  
#             products = json.loads(order.get("products", "[]"))  

#             sales_order_items = []
#             for product in products:
#                 sales_order_items.append({
#                     "item_code": product.get("prodName"),
#                     "qty": product.get("quantity", 1),
#                     "rate": product.get("tranSPPrice", 0),
#                     "amount": product.get("amount", 0)
#                 })

#             sales_order_payload = {
#                 "customer": customer_name,
#                 "transaction_date": order.get("tranDate"),
#                 "delivery_date": order.get("deliveryDate"),
#                 "items": sales_order_items
#             }

#             existing_order = requests.get(
#                 erpnext_api_url,
#                 headers=erpnext_headers,
#                 params={"filters": f'[["Sales Order","name","=","{order.get("tranRefNo")}"]]'}
#             )

#             if existing_order.status_code == 200 and existing_order.json().get("data"):
#                 continue

#             erpnext_response = requests.post(
#                 erpnext_api_url,
#                 headers=erpnext_headers,
#                 json=sales_order_payload
#             )

#             if erpnext_response.status_code != 200:
#                 frappe.log_error(
#                     f"Failed to create Sales Order: {erpnext_response.text}", "Sync Sales Orders"
#                 )

#     except requests.exceptions.RequestException as e:
#         frappe.log_error(f"Failed to fetch data: {e}", "Sync Sales Orders")
#     except Exception as e:
#         frappe.log_error(f"Error syncing sales orders: {e}", "Sync Sales Orders")


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