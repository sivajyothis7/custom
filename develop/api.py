import frappe
import json

# @frappe.whitelist()
# def add_item(code,name,group):
#     add_item = frappe.get_doc({"doctype":"Item",
#         "item_code": code,
#         "item_name": name,
#         "item_group": group,


#     })

#     add_item.insert()
#     frappe.db.commit()
#     return add_item

@frappe.whitelist()
def add_item():
    data = json.loads(frappe.request.data)
    
    item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": data.get("item_code"),
            "item_name": data.get("item_name"),
            "item_group": data.get("item_group")
        })

    item_doc.insert()

@frappe.whitelist()
def add_customer():
    data = json.loads(frappe.request.data)
    
    new_cus = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": data.get("customer_name")
        })

    new_cus.insert()

    # return customer_doc
    # print(f"\n\n{data}\n\n")

    # return