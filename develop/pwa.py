

import frappe
import json
from frappe.utils import getdate, flt, cint
from frappe import _


def ensure_uom_exists(uom):
    """Create UOM if it doesn't exist"""
    if uom and not frappe.db.exists("UOM", uom):
        frappe.get_doc({
            "doctype": "UOM",
            "uom_name": uom
        }).insert(ignore_permissions=True)
        frappe.logger().info(f"✅ Created UOM: {uom}")


def ensure_uom_conversion(item_code, from_uom, to_uom, conversion_factor):
    """Create or update UOM conversion factor for an item"""
    if not from_uom or not to_uom or from_uom == to_uom:
        return
    
    # Check if conversion already exists
    existing = frappe.db.get_value(
        "UOM Conversion Detail",
        {
            "parent": item_code,
            "uom": from_uom
        },
        ["name", "conversion_factor"],
        as_dict=True
    )
    
    if existing:
        if flt(existing.conversion_factor) != flt(conversion_factor):
            frappe.db.set_value(
                "UOM Conversion Detail",
                existing.name,
                "conversion_factor",
                conversion_factor
            )
            frappe.logger().info(f"🔄 Updated UOM conversion for {item_code}: {from_uom} = {conversion_factor} {to_uom}")
    else:
        # Add conversion to item
        item_doc = frappe.get_doc("Item", item_code)
        item_doc.append("uoms", {
            "uom": from_uom,
            "conversion_factor": conversion_factor
        })
        item_doc.save(ignore_permissions=True)
        frappe.logger().info(f"✅ Added UOM conversion for {item_code}: {from_uom} = {conversion_factor} {to_uom}")


def create_or_update_customer(customer_data):
    """Create customer if not exists, update if exists"""
    customer_name = customer_data.get("customer_name")
    
    if frappe.db.exists("Customer", customer_name):
        customer_doc = frappe.get_doc("Customer", customer_name)
        updated = False
        
        if customer_data.get("tax_id") and customer_doc.tax_id != customer_data.get("tax_id"):
            customer_doc.tax_id = customer_data.get("tax_id")
            updated = True
            
        if customer_data.get("customer_group") and customer_doc.customer_group != customer_data.get("customer_group"):
            customer_doc.customer_group = customer_data.get("customer_group")
            updated = True
            
        if updated:
            customer_doc.save(ignore_permissions=True)
            frappe.logger().info(f"🔄 Updated customer: {customer_name}")
    else:
        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": customer_data.get("customer_type", "Company"),
            "customer_group": customer_data.get("customer_group", "Commercial"),
            "territory": customer_data.get("territory", "Saudi Arabia"),
            "tax_id": customer_data.get("tax_id")
        })
        customer_doc.insert(ignore_permissions=True)
        frappe.logger().info(f"✅ Created new customer: {customer_name}")
    
    return customer_name


def ensure_item_exists(item_data):
    """Create item if it doesn't exist, update if exists"""
    item_code = item_data.get("item_code")
    
    if frappe.db.exists("Item", item_code):
        item_doc = frappe.get_doc("Item", item_code)
        updated = False
        
        # Update item name if different
        if item_data.get("item_name") and item_doc.item_name != item_data.get("item_name"):
            item_doc.item_name = item_data.get("item_name")
            updated = True
        
        # Update description if different
        if item_data.get("description") and item_doc.description != item_data.get("description"):
            item_doc.description = item_data.get("description")
            updated = True
            
        if updated:
            item_doc.save(ignore_permissions=True)
            frappe.logger().info(f"🔄 Updated item: {item_code}")
    else:
        # Determine if item should maintain stock
        is_stock_item = item_data.get("is_stock_item", 1)
        
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_data.get("item_name"),
            "item_group": item_data.get("item_group", "Products"),
            "stock_uom": item_data.get("stock_uom", "Nos"),
            "description": item_data.get("description"),
            "is_stock_item": is_stock_item,
            "is_sales_item": 1,
            "include_item_in_manufacturing": 0,
            "valuation_rate": item_data.get("valuation_rate", 0)
        })
        item_doc.insert(ignore_permissions=True)
        frappe.logger().info(f"✅ Created new item: {item_code}")


def get_default_warehouse(company):
    """Get default warehouse for company"""
    warehouse = frappe.db.get_value(
        "Warehouse",
        {
            "company": company,
            "is_group": 0,
            "disabled": 0
        },
        "name"
    )
    
    if not warehouse:
        # Try to find any warehouse for the company
        warehouse = frappe.db.get_value(
            "Warehouse",
            {"company": company, "disabled": 0},
            "name"
        )
    
    return warehouse


def build_consolidated_taxes(company):
    """Build tax rows from company default tax template"""
    tax_rows = []
    
    default_template = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        {"company": company, "is_default": 1},
        "name"
    )
    
    if default_template:
        template_doc = frappe.get_doc("Sales Taxes and Charges Template", default_template)
        for row in template_doc.taxes:
            tax_rows.append({
                "charge_type": row.charge_type,
                "account_head": row.account_head,
                "rate": row.rate,
                "description": row.description or f"Tax @ {row.rate}%"
            })
    
    return tax_rows


# ==================== API ENDPOINTS ====================

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_customers_list():
    """
    API to list all customers
    
    Method: GET
    URL: /api/method/your_app.api.get_customers_list
    
    Query Parameters:
    - customer_group: Filter by customer group
    - territory: Filter by territory
    - disabled: 0 or 1
    
    Returns:
        JSON with list of customers
    """
    try:
        # Get query parameters
        filters = {}
        
        customer_group = frappe.form_dict.get("customer_group")
        if customer_group:
            filters["customer_group"] = customer_group
            
        territory = frappe.form_dict.get("territory")
        if territory:
            filters["territory"] = territory
            
        disabled = frappe.form_dict.get("disabled")
        if disabled is not None:
            filters["disabled"] = cint(disabled)
        
        customers = frappe.get_all(
            "Customer",
            filters=filters,
            fields=[
                "name",
                "customer_name",
                "customer_type",
                "customer_group",
                "territory",
                "tax_id",
                "disabled",
                "creation",
                "modified"
            ],
            order_by="customer_name asc"
        )
        
        return {
            "status": "success",
            "count": len(customers),
            "data": customers
        }
        
    except Exception as e:
        frappe.log_error("Get Customers Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_customer():
    """
    API to create a new customer
    
    Method: POST
    URL: /api/method/your_app.api.create_customer
    Content-Type: application/json
    
    Body:
    {
        "customer_name": "ABC Company",
        "customer_type": "Company",
        "customer_group": "Commercial",
        "territory": "Saudi Arabia",
        "tax_id": "300000000000003"
    }
    
    Returns:
        JSON with customer details
    """
    try:
        # Parse JSON body
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            data = frappe.form_dict
        
        customer_name = data.get("customer_name")
        if not customer_name:
            return {
                "status": "error",
                "message": "customer_name is required"
            }
        
        if frappe.db.exists("Customer", customer_name):
            return {
                "status": "exists",
                "message": f"Customer '{customer_name}' already exists",
                "data": {
                    "customer_name": customer_name
                }
            }
        
        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": data.get("customer_type", "Company"),
            "customer_group": data.get("customer_group", "Commercial"),
            "territory": data.get("territory", "Saudi Arabia"),
            "tax_id": data.get("tax_id")
        })
        customer_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Customer '{customer_name}' created successfully",
            "data": {
                "customer_name": customer_doc.name,
                "customer_type": customer_doc.customer_type,
                "customer_group": customer_doc.customer_group,
                "territory": customer_doc.territory,
                "tax_id": customer_doc.tax_id
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Customer Creation Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=True)
def get_warehouse_list(company=None):
    """
    Return all warehouses filtered by company (if provided).
    """

    filters = {}
    if company:
        filters["company"] = company

    warehouses = frappe.get_all(
        "Warehouse",
        filters=filters,
        fields=["name", "warehouse_name", "company", "is_group"],
        order_by="warehouse_name asc"
    )

    return {
        "status": "success",
        "message": "Warehouse list fetched",
        "warehouses": warehouses
    }






@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_sales_invoice():
    """
    Create or update a Sales Invoice with:
    - Item creation
    - Auto-detected default Sales Taxes & Charges template
    - Manual taxes fallback
    - Shipping & extra charges
    - Stock update
    - VAT summary response
    """

    try:
        # ------------------------------
        # Parse Request JSON
        # ------------------------------
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict

        required_fields = ["customer_name", "company", "items"]
        for field in required_fields:
            if not data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}

        customer_name = data["customer_name"]
        company = data["company"]

        # ------------------------------
        # Validate Company
        # ------------------------------
        if not frappe.db.exists("Company", company):
            return {"status": "error", "message": f"Company '{company}' not found"}

        company_doc = frappe.get_doc("Company", company)
        currency = company_doc.default_currency
        income_account = company_doc.default_income_account
        receivable_account = company_doc.default_receivable_account
        cost_center = company_doc.cost_center

        if not income_account or not receivable_account:
            return {"status": "error", "message": "Company missing default accounts"}

        # ------------------------------
        # Customer Create/Update
        # ------------------------------
        create_or_update_customer({
            "customer_name": customer_name,
            "customer_type": data.get("customer_type", "Company"),
            "customer_group": data.get("customer_group", "Commercial"),
            "territory": data.get("territory", "Saudi Arabia"),
            "tax_id": data.get("tax_id")
        })

        posting_date = getdate(data.get("posting_date") or getdate())
        due_date = getdate(data.get("due_date") or posting_date)

        update_stock = cint(data.get("update_stock", 0))
        target_warehouse = data.get("target_warehouse") or get_default_warehouse(company)

        # ------------------------------
        # Items Processing
        # ------------------------------
        items_data = data.get("items")
        invoice_items = []

        for item in items_data:
            item_code = item.get("item_code")
            if not item_code:
                continue

            ensure_uom_exists(item.get("uom", "Nos"))
            ensure_uom_exists(item.get("stock_uom", item.get("uom", "Nos")))

            ensure_item_exists({
                "item_code": item_code,
                "item_name": item.get("item_name") or item_code,
                "description": item.get("description") or item_code,
                "stock_uom": item.get("stock_uom", "Nos"),
                "valuation_rate": item.get("valuation_rate", 0),
                "item_group": item.get("item_group", "Products"),
                "is_stock_item": update_stock
            })

            row = {
                "item_code": item_code,
                "item_name": item.get("item_name"),
                "description": item.get("description"),
                "qty": flt(item.get("qty", 1)),
                "rate": flt(item.get("rate", 0)),
                "uom": item.get("uom", "Nos"),
                "stock_uom": item.get("stock_uom", "Nos"),
                "conversion_factor": item.get("conversion_factor", 1),
                "income_account": income_account,
                "cost_center": cost_center
            }

            if update_stock and target_warehouse:
                row["warehouse"] = target_warehouse

            invoice_items.append(row)

        # --------------------------------------------------
        # AUTO DEFAULT TAX TEMPLATE (NO HARDCODE)
        # --------------------------------------------------
        tax_rows = []

        # 1️⃣ Get default template for the company
        resolved_tax_template = frappe.db.get_value(
            "Sales Taxes and Charges Template",
            {
                "company": company,
                "is_default": 1,
                "disabled": 0
            },
            "name"
        )

        # 2️⃣ If no default → error
        if not resolved_tax_template:
            return {
                "status": "error",
                "message": f"No default Sales Taxes and Charges Template found for company '{company}'"
            }

        # 3️⃣ Load taxes from template
        tpl = frappe.get_doc("Sales Taxes and Charges Template", resolved_tax_template)
        for t in tpl.taxes:
            tax_rows.append({
                "charge_type": t.charge_type,
                "account_head": t.account_head,
                "description": t.description,
                "rate": t.rate,
                "tax_amount": t.tax_amount,
                "cost_center": cost_center
            })

        # ------------------------------
        # CREATE OR UPDATE INVOICE
        # ------------------------------
        invoice_name = data.get("invoice_name")

        if invoice_name and frappe.db.exists("Sales Invoice", invoice_name):
            doc = frappe.get_doc("Sales Invoice", invoice_name)

            if doc.docstatus != 0:
                return {"status": "error", "message": "Invoice submitted; cannot update"}

            doc.customer = customer_name
            doc.company = company
            doc.posting_date = posting_date
            doc.due_date = due_date
            doc.update_stock = update_stock

            if target_warehouse:
                doc.set_warehouse = target_warehouse

            doc.set("items", invoice_items)
            doc.set("taxes", tax_rows)

            # Assign default template
            doc.taxes_and_charges = resolved_tax_template

            doc.save(ignore_permissions=True)
            frappe.db.commit()

        else:
            invoice_data = {
                "doctype": "Sales Invoice",
                "customer": customer_name,
                "company": company,
                "posting_date": posting_date,
                "due_date": due_date,
                "currency": currency,
                "debit_to": receivable_account,
                "conversion_rate": 1,
                "ignore_pricing_rule": 1,
                "update_stock": update_stock,
                "items": invoice_items,
                "taxes": tax_rows,
                "taxes_and_charges": resolved_tax_template
            }

            if data.get("naming_series"):
                invoice_data["naming_series"] = data["naming_series"]

            if target_warehouse:
                invoice_data["set_warehouse"] = target_warehouse

            doc = frappe.get_doc(invoice_data)
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

        # ------------------------------
        # RESPONSE WITH VAT DETAILS
        # ------------------------------
        return {
            "status": "success",
            "message": f"Invoice {doc.name} created successfully",
            "data": {
                "invoice_name": doc.name,
                "customer": doc.customer,
                "company": doc.company,

                "posting_date": str(doc.posting_date),
                "due_date": str(doc.due_date),

                "net_total": doc.net_total,
                "vat_amount": doc.total_taxes_and_charges,
                "tax_total": doc.total_taxes_and_charges,
                "grand_total": doc.grand_total,
                "rounded_total": doc.rounded_total or doc.grand_total,
                "rounding_adjustment": doc.rounding_adjustment or 0,
                "outstanding_amount": doc.outstanding_amount,

                # Return default template name
                "taxes_and_charges": resolved_tax_template,

                "items": [
                    {
                        "item_code": i.item_code,
                        "qty": i.qty,
                        "rate": i.rate,
                        "amount": i.amount,
                        "uom": i.uom,
                        "description": i.description
                    }
                    for i in doc.items
                ],

                "taxes": [
                    {
                        "description": t.description,
                        "charge_type": t.charge_type,
                        "account_head": t.account_head,
                        "cost_center": t.cost_center,
                        "rate": t.rate,
                        "tax_amount": t.tax_amount
                    }
                    for t in doc.taxes
                ]
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Sales Invoice API Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_invoice_details():
    """
    API to get invoice details
    
    Method: GET
    URL: /api/method/your_app.api.get_invoice_details
    
    Query Parameters:
    - invoice_name: Sales Invoice name (required)
    
    Returns:
        JSON with invoice details
    """
    try:
        invoice_name = frappe.form_dict.get("invoice_name")
        
        if not invoice_name:
            return {
                "status": "error",
                "message": "invoice_name is required"
            }
        
        if not frappe.db.exists("Sales Invoice", invoice_name):
            return {
                "status": "error",
                "message": f"Invoice {invoice_name} not found"
            }
        
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Build items list
        items = []
        for item in doc.items:
            items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "amount": item.amount,
                "warehouse": item.warehouse
            })
        
        # Build taxes list
        taxes = []
        for tax in doc.taxes:
            taxes.append({
                "account_head": tax.account_head,
                "rate": tax.rate,
                "tax_amount": tax.tax_amount
            })
        
        return {
            "status": "success",
            "data": {
                "invoice_name": doc.name,
                "customer": doc.customer,
                "customer_name": doc.customer_name,
                "company": doc.company,
                "posting_date": str(doc.posting_date),
                "due_date": str(doc.due_date),
                "status": doc.status,
                "docstatus": doc.docstatus,
                "grand_total": doc.grand_total,
                "outstanding_amount": doc.outstanding_amount,
                "items": items,
                "taxes": taxes
            }
        }
        
    except Exception as e:
        frappe.log_error("Get Invoice Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_sales_invoice():
    """
    API to submit a sales invoice
    
    Method: POST
    URL: /api/method/your_app.api.submit_sales_invoice
    Content-Type: application/json
    
    Body:
    {
        "invoice_name": "SINV-00001"
    }
    
    Returns:
        JSON with submission result
    """
    try:
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            data = frappe.form_dict
        
        invoice_name = data.get("invoice_name")
        
        if not invoice_name:
            return {
                "status": "error",
                "message": "invoice_name is required"
            }
        
        if not frappe.db.exists("Sales Invoice", invoice_name):
            return {
                "status": "error",
                "message": f"Invoice {invoice_name} not found"
            }
        
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        
        if doc.docstatus == 1:
            return {
                "status": "error",
                "message": f"Invoice {invoice_name} is already submitted"
            }
        
        doc.submit()
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Invoice {invoice_name} submitted successfully",
            "data": {
                "invoice_name": doc.name,
                "docstatus": doc.docstatus,
                "status": doc.status
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Invoice Submit Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }