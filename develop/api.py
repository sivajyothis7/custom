import frappe
import json


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
            "customer_name": data.get("customer_name"),
        })

    new_cus.insert()

@frappe.whitelist()
def add_sales_invoice():
    data = json.loads(frappe.request.data)

    sales_invoice_doc = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": data.get("customer"),
        "posting_date": data.get("posting_date"),
        "items": data.get("items"), 
    })


    sales_invoice_doc.insert()
    sales_invoice_doc.submit()  