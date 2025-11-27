import frappe
import json
from frappe.utils import getdate, flt, cint
from frappe import _
import hashlib
import secrets
from datetime import datetime, timedelta
import frappe
import json
from frappe.utils import getdate, flt, cint, nowdate, add_days, get_datetime
from frappe import _

# ==================== AUTHENTICATION APIs ====================

@frappe.whitelist(allow_guest=True, methods=["POST"])
def login():
    """
    Custom login API using email and password
    
    Method: POST
    URL: /api/method/your_app.api.login
    Content-Type: application/json
    
    Body:
    {
        "email": "user@example.com",
        "password": "your_password"
    }
    
    Returns:
        JSON with authentication token and user details
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            return {
                "status": "error",
                "message": "Email and password are required"
            }
        
        # Authenticate user
        try:
            frappe.auth.check_password(email, password)
        except frappe.exceptions.AuthenticationError:
            return {
                "status": "error",
                "message": "Invalid email or password"
            }
        
        # Get user details
        user = frappe.get_doc("User", email)
        
        if user.enabled == 0:
            return {
                "status": "error",
                "message": "User account is disabled"
            }
        
        # Generate API token
        api_key = user.api_key
        api_secret = None
        
        # Generate new API key and secret if not exists
        if not api_key:
            api_key = frappe.generate_hash(length=15)
            api_secret = frappe.generate_hash(length=15)
            
            user.api_key = api_key
            user.api_secret = api_secret
            user.save(ignore_permissions=True)
            frappe.db.commit()
        else:
            # Get existing API secret
            api_secret = user.get_password('api_secret')
        
        # Create session token (alternative to API key/secret)
        token = generate_custom_token(email)
        
        return {
            "status": "success",
            "message": "Login successful",
            "data": {
                "user": email,
                "full_name": user.full_name,
                "user_image": user.user_image,
                "token": token,
                "api_key": api_key,
                "api_secret": api_secret,
                "expires_in": 86400  # 24 hours
            }
        }
        
    except Exception as e:
        frappe.log_error("Login API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def validate_token():
    """
    Validate authentication token
    
    Method: POST
    URL: /api/method/your_app.api.validate_token
    Content-Type: application/json
    
    Body:
    {
        "token": "your_token_here"
    }
    
    Returns:
        JSON with validation status and user details
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        token = data.get("token")
        
        if not token:
            return {
                "status": "error",
                "message": "Token is required"
            }
        
        user_email = verify_custom_token(token)
        
        if not user_email:
            return {
                "status": "error",
                "message": "Invalid or expired token"
            }
        
        user = frappe.get_doc("User", user_email)
        
        return {
            "status": "success",
            "message": "Token is valid",
            "data": {
                "user": user_email,
                "full_name": user.full_name,
                "user_image": user.user_image
            }
        }
        
    except Exception as e:
        frappe.log_error("Validate Token Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def logout():
    """
    Logout API - invalidates the current session token
    
    Method: POST
    URL: /api/method/your_app.api.logout
    Headers:
        Authorization: Bearer <token>
    
    Returns:
        JSON with logout confirmation
    """
    try:
        # Get token from Authorization header
        auth_header = frappe.get_request_header("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            invalidate_custom_token(token)
        
        frappe.local.login_manager.logout()
        
        return {
            "status": "success",
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        frappe.log_error("Logout API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


def generate_custom_token(user_email):
    """Generate a custom token for user authentication"""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    
    # Store token in custom doctype or cache
    # For simplicity, using frappe.cache
    frappe.cache().set_value(
        f"auth_token:{token}",
        {
            "user": user_email,
            "expiry": expiry.isoformat()
        },
        expires_in_sec=86400  # 24 hours
    )
    
    return token


def verify_custom_token(token):
    """Verify custom token and return user email"""
    token_data = frappe.cache().get_value(f"auth_token:{token}")
    
    if not token_data:
        return None
    
    expiry = datetime.fromisoformat(token_data["expiry"])
    if datetime.now() > expiry:
        frappe.cache().delete_value(f"auth_token:{token}")
        return None
    
    return token_data["user"]


def invalidate_custom_token(token):
    """Invalidate a custom token"""
    frappe.cache().delete_value(f"auth_token:{token}")


# ==================== ITEM APIs ====================

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_items_list():
    """
    API to list all items with filtering and pagination
    
    Method: GET
    URL: /api/method/your_app.api.get_items_list
    
    Query Parameters:
    - item_group: Filter by item group
    - is_stock_item: 0 or 1
    - is_sales_item: 0 or 1
    - disabled: 0 or 1
    - search: Search by item_code or item_name
    - limit: Number of items per page (default: 20)
    - offset: Starting position (default: 0)
    - order_by: Sort field (default: item_name)
    - order: asc or desc (default: asc)
    
    Returns:
        JSON with list of items
    """
    try:
        filters = {}
        
        # Apply filters
        item_group = frappe.form_dict.get("item_group")
        if item_group:
            filters["item_group"] = item_group
        
        is_stock_item = frappe.form_dict.get("is_stock_item")
        if is_stock_item is not None:
            filters["is_stock_item"] = cint(is_stock_item)
        
        is_sales_item = frappe.form_dict.get("is_sales_item")
        if is_sales_item is not None:
            filters["is_sales_item"] = cint(is_sales_item)
        
        disabled = frappe.form_dict.get("disabled")
        if disabled is not None:
            filters["disabled"] = cint(disabled)
        
        # Search functionality
        search = frappe.form_dict.get("search")
        if search:
            filters["item_code"] = ["like", f"%{search}%"]
        
        # Pagination
        limit = cint(frappe.form_dict.get("limit", 20))
        offset = cint(frappe.form_dict.get("offset", 0))
        
        # Ordering
        order_by = frappe.form_dict.get("order_by", "item_name")
        order = frappe.form_dict.get("order", "asc")
        
        # Get items
        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=[
                "name",
                "item_code",
                "item_name",
                "item_group",
                "stock_uom",
                "description",
                "is_stock_item",
                "is_sales_item",
                "valuation_rate",
                "standard_rate",
                "image",
                "disabled",
                "creation",
                "modified"
            ],
            order_by=f"{order_by} {order}",
            limit_page_length=limit,
            limit_start=offset
        )
        
        # Get total count
        total_count = frappe.db.count("Item", filters=filters)
        
        return {
            "status": "success",
            "count": len(items),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "data": items
        }
        
    except Exception as e:
        frappe.log_error("Get Items List Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_item_details():
    """
    API to get detailed information about a specific item
    
    Method: GET
    URL: /api/method/your_app.api.get_item_details?item_code=ITEM-001
    
    Query Parameters:
    - item_code: Item code (required)
    
    Returns:
        JSON with item details including UOM conversions and stock levels
    """
    try:
        item_code = frappe.form_dict.get("item_code")
        
        if not item_code:
            return {
                "status": "error",
                "message": "item_code is required"
            }
        
        if not frappe.db.exists("Item", item_code):
            return {
                "status": "error",
                "message": f"Item '{item_code}' not found"
            }
        
        item = frappe.get_doc("Item", item_code)
        
        # Get UOM conversions
        uom_conversions = []
        for uom in item.uoms:
            uom_conversions.append({
                "uom": uom.uom,
                "conversion_factor": uom.conversion_factor
            })
        
        # Get stock levels by warehouse
        stock_levels = []
        if item.is_stock_item:
            bins = frappe.get_all(
                "Bin",
                filters={"item_code": item_code},
                fields=[
                    "warehouse",
                    "actual_qty",
                    "reserved_qty",
                    "ordered_qty",
                    "projected_qty"
                ]
            )
            stock_levels = bins
        
        # Get item prices
        item_prices = frappe.get_all(
            "Item Price",
            filters={"item_code": item_code},
            fields=[
                "price_list",
                "price_list_rate",
                "currency",
                "valid_from",
                "valid_upto"
            ]
        )
        
        return {
            "status": "success",
            "data": {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "stock_uom": item.stock_uom,
                "description": item.description,
                "is_stock_item": item.is_stock_item,
                "is_sales_item": item.is_sales_item,
                "valuation_rate": item.valuation_rate,
                "standard_rate": item.standard_rate,
                "image": item.image,
                "disabled": item.disabled,
                "has_variants": item.has_variants,
                "variant_of": item.variant_of,
                "uom_conversions": uom_conversions,
                "stock_levels": stock_levels,
                "item_prices": item_prices,
                "creation": str(item.creation),
                "modified": str(item.modified)
            }
        }
        
    except Exception as e:
        frappe.log_error("Get Item Details Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_item():
    """
    API to create a new item
    
    Method: POST
    URL: /api/method/your_app.api.create_item
    Content-Type: application/json
    
    Body:
    {
        "item_code": "ITEM-001",
        "item_name": "Product Name",
        "item_group": "Products",
        "stock_uom": "Nos",
        "description": "Product description",
        "is_stock_item": 1,
        "is_sales_item": 1,
        "valuation_rate": 100,
        "standard_rate": 150
    }
    
    Returns:
        JSON with created item details
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        item_code = data.get("item_code")
        item_name = data.get("item_name")
        
        if not item_code or not item_name:
            return {
                "status": "error",
                "message": "item_code and item_name are required"
            }
        
        if frappe.db.exists("Item", item_code):
            return {
                "status": "error",
                "message": f"Item '{item_code}' already exists"
            }
        
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": data.get("item_group", "Products"),
            "stock_uom": data.get("stock_uom", "Nos"),
            "description": data.get("description"),
            "is_stock_item": cint(data.get("is_stock_item", 1)),
            "is_sales_item": cint(data.get("is_sales_item", 1)),
            "valuation_rate": flt(data.get("valuation_rate", 0)),
            "standard_rate": flt(data.get("standard_rate", 0))
        })
        
        item_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Item '{item_code}' created successfully",
            "data": {
                "item_code": item_doc.item_code,
                "item_name": item_doc.item_name,
                "item_group": item_doc.item_group
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Create Item API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["PUT", "POST"])
def update_item():
    """
    API to update an existing item
    
    Method: PUT or POST
    URL: /api/method/your_app.api.update_item
    Content-Type: application/json
    
    Body:
    {
        "item_code": "ITEM-001",
        "item_name": "Updated Product Name",
        "description": "Updated description",
        "standard_rate": 200
    }
    
    Returns:
        JSON with updated item details
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        item_code = data.get("item_code")
        
        if not item_code:
            return {
                "status": "error",
                "message": "item_code is required"
            }
        
        if not frappe.db.exists("Item", item_code):
            return {
                "status": "error",
                "message": f"Item '{item_code}' not found"
            }
        
        item_doc = frappe.get_doc("Item", item_code)
        
        # Update fields if provided
        updatable_fields = [
            "item_name", "description", "standard_rate", 
            "valuation_rate", "disabled"
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(item_doc, field, data[field])
        
        item_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Item '{item_code}' updated successfully",
            "data": {
                "item_code": item_doc.item_code,
                "item_name": item_doc.item_name,
                "standard_rate": item_doc.standard_rate
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Update Item API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }




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
        
        if item_data.get("item_name") and item_doc.item_name != item_data.get("item_name"):
            item_doc.item_name = item_data.get("item_name")
            updated = True
        
        if item_data.get("description") and item_doc.description != item_data.get("description"):
            item_doc.description = item_data.get("description")
            updated = True
            
        if updated:
            item_doc.save(ignore_permissions=True)
            frappe.logger().info(f"🔄 Updated item: {item_code}")
    else:
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


@frappe.whitelist()
def get_sales_invoice_list():
    """
    Fetch Sales Invoice list using URL query parameters.
    Supports:
    - customer
    - status
    - start_date, end_date
    - limit, offset
    Also returns VAT (tax total) separately.
    """

    customer = frappe.form_dict.get("customer")
    status = frappe.form_dict.get("status")
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")

    limit = cint(frappe.form_dict.get("limit", 50))
    offset = cint(frappe.form_dict.get("offset", 0))

    filters = {}

    if customer:
        filters["customer"] = customer

    if status:
        filters["status"] = status

    if start_date and end_date:
        filters["posting_date"] = ["between", [start_date, end_date]]

    invoice_names = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=["name"],
        order_by="posting_date desc",
        limit_page_length=limit,
        limit_start=offset
    )

    invoice_list = []

    for inv in invoice_names:
        doc = frappe.get_doc("Sales Invoice", inv.name)

        invoice_list.append({
            "name": doc.name,
            "customer": doc.customer,
            "company": doc.company,
            "posting_date": doc.posting_date,
            "due_date": doc.due_date,

            "net_total": doc.net_total,
            "tax_total": doc.total_taxes_and_charges,      
            "grand_total": doc.grand_total,
            "rounded_total": doc.rounded_total or doc.grand_total,

            "outstanding_amount": doc.outstanding_amount,
            "status": doc.status
        })

    return {
        "status_code": 200,
        "count": len(invoice_list),
        "invoices": invoice_list
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
        
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict

        required_fields = ["customer_name", "company", "items"]
        for field in required_fields:
            if not data.get(field):
                return {"status": "error", "message": f"'{field}' is required"}

        customer_name = data["customer_name"]
        company = data["company"]

       
        if not frappe.db.exists("Company", company):
            return {"status": "error", "message": f"Company '{company}' not found"}

        company_doc = frappe.get_doc("Company", company)
        currency = company_doc.default_currency
        income_account = company_doc.default_income_account
        receivable_account = company_doc.default_receivable_account
        cost_center = company_doc.cost_center

        if not income_account or not receivable_account:
            return {"status": "error", "message": "Company missing default accounts"}

      
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

        
        tax_rows = []

        resolved_tax_template = frappe.db.get_value(
            "Sales Taxes and Charges Template",
            {
                "company": company,
                "is_default": 1,
                "disabled": 0
            },
            "name"
        )

        if not resolved_tax_template:
            return {
                "status": "error",
                "message": f"No default Sales Taxes and Charges Template found for company '{company}'"
            }

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
    API to get Sales Invoice details (query-based)
    
    Usage:
    GET /api/method/develop.api.get_invoice_details?invoice_name=SINV-00010
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
                "message": f"Invoice '{invoice_name}' not found"
            }

        doc = frappe.get_doc("Sales Invoice", invoice_name)

       
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

       
        taxes = []
        for tax in doc.taxes:
            taxes.append({
                "description": tax.description,
                "charge_type": tax.charge_type,
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

                "net_total": doc.net_total,
                "vat_amount": doc.total_taxes_and_charges,
                "grand_total": doc.grand_total,
                "rounded_total": doc.rounded_total or doc.grand_total,
                "rounding_adjustment": doc.rounding_adjustment or 0,
                "outstanding_amount": doc.outstanding_amount,

                "items": items,
                "taxes": taxes
            }
        }

    except Exception as e:
        frappe.log_error("Get Invoice Details Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_sales_invoice():
    """
    Final submission logic:
    - Submit invoice first
    - If custom_mode_of_payment = Credit → no payment entry
    - If Cash/Bank/POS → create Payment Entry AFTER invoice is submitted
    """

    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict

        invoice_name = data.get("invoice_name")

        if not invoice_name:
            return {"status": "error", "message": "invoice_name is required"}

        if not frappe.db.exists("Sales Invoice", invoice_name):
            return {"status": "error", "message": f"Invoice {invoice_name} not found"}

        inv = frappe.get_doc("Sales Invoice", invoice_name)

        if inv.docstatus == 1:
            return {"status": "error", "message": "Invoice already submitted"}

        payment_mode = inv.get("custom_mode_of_payment")
        if not payment_mode:
            return {"status": "error", "message": "custom_mode_of_payment is required"}

        payment_mode_lower = payment_mode.lower().strip()

      
        inv.submit()
        frappe.db.commit()

       
        if payment_mode_lower == "credit":
            return {
                "status": "success",
                "message": "Invoice submitted successfully (CREDIT). No Payment Entry created.",
                "data": {
                    "invoice_name": inv.name,
                    "payment_entry": None
                }
            }

      

        receivable_account = frappe.db.get_value(
            "Company", inv.company, "default_receivable_account"
        )

        if not receivable_account:
            return {"status": "error", "message": "Default Receivable Account missing in Company settings"}

        payment_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": payment_mode, "company": inv.company},
            "default_account"
        )

        if not payment_account:
            return {
                "status": "error",
                "message": f"No account found under Mode of Payment '{payment_mode}'. Configure it under Mode of Payment → Accounts."
            }

       
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "posting_date": inv.posting_date,
            "company": inv.company,
            "party_type": "Customer",
            "party": inv.customer,

            "paid_from": receivable_account,     
            "paid_to": payment_account,            

            "mode_of_payment": payment_mode,

            "paid_amount": inv.grand_total,
            "received_amount": inv.grand_total,

            "references": [
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": inv.name,
                    "total_amount": inv.grand_total,
                    "outstanding_amount": inv.outstanding_amount,
                    "exchange_rate": 1,
                    "allocated_amount": inv.grand_total
                }
            ]
        })

        pe.insert(ignore_permissions=True)
        pe.submit()
        frappe.db.commit()

       
        return {
            "status": "success",
            "message": "Invoice and Payment Entry submitted successfully",
            "data": {
                "invoice_name": inv.name,
                "payment_entry": pe.name
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Submit Sales Invoice Error")
        return {"status": "error", "message": str(e)}






# ==================== PAYMENT ENTRY APIs ====================

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_payment_entries_list():
    """
    API to list all payment entries with filtering and pagination
    
    Method: GET
    URL: /api/method/your_app.api.get_payment_entries_list
    
    Query Parameters:
    - party: Filter by customer name
    - party_type: Customer/Supplier (default: Customer)
    - payment_type: Receive/Pay
    - mode_of_payment: Filter by payment mode
    - from_date: Start date (YYYY-MM-DD)
    - to_date: End date (YYYY-MM-DD)
    - status: Filter by docstatus (0=Draft, 1=Submitted, 2=Cancelled)
    - limit: Number of entries per page (default: 20)
    - offset: Starting position (default: 0)
    - order_by: Sort field (default: posting_date)
    - order: asc or desc (default: desc)
    
    Returns:
        JSON with list of payment entries
    """
    try:
        filters = {}
        
        # Party filters
        party = frappe.form_dict.get("party")
        if party:
            filters["party"] = party
        
        party_type = frappe.form_dict.get("party_type", "Customer")
        filters["party_type"] = party_type
        
        # Payment type filter
        payment_type = frappe.form_dict.get("payment_type")
        if payment_type:
            filters["payment_type"] = payment_type
        
        # Mode of payment filter
        mode_of_payment = frappe.form_dict.get("mode_of_payment")
        if mode_of_payment:
            filters["mode_of_payment"] = mode_of_payment
        
        # Status filter
        status = frappe.form_dict.get("status")
        if status is not None:
            filters["docstatus"] = cint(status)
        
        # Date range filters
        from_date = frappe.form_dict.get("from_date")
        to_date = frappe.form_dict.get("to_date")
        
        if from_date and to_date:
            filters["posting_date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["posting_date"] = [">=", from_date]
        elif to_date:
            filters["posting_date"] = ["<=", to_date]
        
        # Pagination
        limit = cint(frappe.form_dict.get("limit", 20))
        offset = cint(frappe.form_dict.get("offset", 0))
        
        # Ordering
        order_by = frappe.form_dict.get("order_by", "posting_date")
        order = frappe.form_dict.get("order", "desc")
        
        # Get payment entries
        payment_entries = frappe.get_all(
            "Payment Entry",
            filters=filters,
            fields=[
                "name",
                "posting_date",
                "payment_type",
                "party_type",
                "party",
                "party_name",
                "paid_amount",
                "received_amount",
                "paid_from",
                "paid_to",
                "mode_of_payment",
                "reference_no",
                "reference_date",
                "docstatus",
                "creation",
                "modified",
                "company"
            ],
            order_by=f"{order_by} {order}",
            limit_page_length=limit,
            limit_start=offset
        )
        
        # Get total count
        total_count = frappe.db.count("Payment Entry", filters=filters)
        
        # Add status labels
        for pe in payment_entries:
            if pe.docstatus == 0:
                pe["status"] = "Draft"
            elif pe.docstatus == 1:
                pe["status"] = "Submitted"
            elif pe.docstatus == 2:
                pe["status"] = "Cancelled"
        
        return {
            "status": "success",
            "count": len(payment_entries),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "data": payment_entries
        }
        
    except Exception as e:
        frappe.log_error("Get Payment Entries Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_payment_entry_details():
    """
    API to get detailed information about a specific payment entry
    
    Method: GET
    URL: /api/method/your_app.api.get_payment_entry_details?payment_entry=PE-00001
    
    Query Parameters:
    - payment_entry: Payment Entry name (required)
    
    Returns:
        JSON with payment entry details including references
    """
    try:
        payment_entry_name = frappe.form_dict.get("payment_entry")
        
        if not payment_entry_name:
            return {
                "status": "error",
                "message": "payment_entry is required"
            }
        
        if not frappe.db.exists("Payment Entry", payment_entry_name):
            return {
                "status": "error",
                "message": f"Payment Entry '{payment_entry_name}' not found"
            }
        
        pe = frappe.get_doc("Payment Entry", payment_entry_name)
        
        # Get references (invoices)
        references = []
        for ref in pe.references:
            references.append({
                "reference_doctype": ref.reference_doctype,
                "reference_name": ref.reference_name,
                "total_amount": ref.total_amount,
                "outstanding_amount": ref.outstanding_amount,
                "allocated_amount": ref.allocated_amount,
                "exchange_rate": ref.exchange_rate
            })
        
        # Get deductions if any
        deductions = []
        if hasattr(pe, 'deductions'):
            for ded in pe.deductions:
                deductions.append({
                    "account": ded.account,
                    "cost_center": ded.cost_center,
                    "amount": ded.amount,
                    "description": ded.description
                })
        
        return {
            "status": "success",
            "data": {
                "name": pe.name,
                "posting_date": str(pe.posting_date),
                "payment_type": pe.payment_type,
                "party_type": pe.party_type,
                "party": pe.party,
                "party_name": pe.party_name,
                "company": pe.company,
                
                "paid_from": pe.paid_from,
                "paid_from_account_currency": pe.paid_from_account_currency,
                "paid_to": pe.paid_to,
                "paid_to_account_currency": pe.paid_to_account_currency,
                
                "paid_amount": pe.paid_amount,
                "received_amount": pe.received_amount,
                "source_exchange_rate": pe.source_exchange_rate,
                "target_exchange_rate": pe.target_exchange_rate,
                
                "mode_of_payment": pe.mode_of_payment,
                "reference_no": pe.reference_no,
                "reference_date": str(pe.reference_date) if pe.reference_date else None,
                
                "total_allocated_amount": pe.total_allocated_amount,
                "unallocated_amount": pe.unallocated_amount,
                "difference_amount": pe.difference_amount,
                
                "docstatus": pe.docstatus,
                "status": "Draft" if pe.docstatus == 0 else "Submitted" if pe.docstatus == 1 else "Cancelled",
                
                "remarks": pe.remarks,
                
                "references": references,
                "deductions": deductions,
                
                "creation": str(pe.creation),
                "modified": str(pe.modified)
            }
        }
        
    except Exception as e:
        frappe.log_error("Get Payment Entry Details Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_payment_entry():
    """
    API to create a payment entry against single or multiple invoices
    
    Method: POST
    URL: /api/method/your_app.api.create_payment_entry
    Content-Type: application/json
    
    Body:
    {
        "party_type": "Customer",
        "party": "CUST-001",
        "payment_type": "Receive",
        "posting_date": "2024-01-15",
        "mode_of_payment": "Cash",
        "paid_amount": 1500.00,
        "company": "Your Company",
        "reference_no": "CHQ-12345",
        "reference_date": "2024-01-15",
        "remarks": "Payment received",
        "invoices": [
            {
                "reference_name": "SINV-00001",
                "allocated_amount": 1000.00
            },
            {
                "reference_name": "SINV-00002",
                "allocated_amount": 500.00
            }
        ]
    }
    
    Note: If invoices array is empty or not provided, creates an unallocated payment
    
    Returns:
        JSON with created payment entry details
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        # Validate required fields
        required_fields = ["party_type", "party", "payment_type", "paid_amount", "mode_of_payment"]
        for field in required_fields:
            if not data.get(field):
                return {
                    "status": "error",
                    "message": f"{field} is required"
                }
        
        party_type = data.get("party_type")
        party = data.get("party")
        payment_type = data.get("payment_type")
        company = data.get("company") or frappe.defaults.get_user_default("Company")
        
        # Validate party exists
        if not frappe.db.exists(party_type, party):
            return {
                "status": "error",
                "message": f"{party_type} '{party}' not found"
            }
        
        # Get accounts based on payment type
        if payment_type == "Receive":
            receivable_account = frappe.db.get_value(
                "Company", company, "default_receivable_account"
            )
            if not receivable_account:
                return {
                    "status": "error",
                    "message": "Default Receivable Account missing in Company settings"
                }
            paid_from = receivable_account
        else:
            payable_account = frappe.db.get_value(
                "Company", company, "default_payable_account"
            )
            if not payable_account:
                return {
                    "status": "error",
                    "message": "Default Payable Account missing in Company settings"
                }
            paid_from = payable_account
        
        # Get payment account from mode of payment
        payment_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": data.get("mode_of_payment"), "company": company},
            "default_account"
        )
        
        if not payment_account:
            return {
                "status": "error",
                "message": f"No account found for Mode of Payment '{data.get('mode_of_payment')}'"
            }
        
        paid_to = payment_account if payment_type == "Receive" else receivable_account or payable_account
        
        # Create payment entry
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": payment_type,
            "posting_date": data.get("posting_date", nowdate()),
            "company": company,
            "party_type": party_type,
            "party": party,
            
            "paid_from": paid_from,
            "paid_to": paid_to,
            
            "mode_of_payment": data.get("mode_of_payment"),
            "paid_amount": flt(data.get("paid_amount")),
            "received_amount": flt(data.get("received_amount", data.get("paid_amount"))),
            
            "reference_no": data.get("reference_no"),
            "reference_date": data.get("reference_date"),
            "remarks": data.get("remarks", "Payment Entry created via API")
        })
        
        # Add invoice references if provided
        invoices = data.get("invoices", [])
        total_allocated = 0
        
        for inv_data in invoices:
            invoice_name = inv_data.get("reference_name")
            allocated_amount = flt(inv_data.get("allocated_amount", 0))
            
            if not invoice_name:
                continue
            
            # Determine reference doctype based on payment type
            if payment_type == "Receive":
                ref_doctype = "Sales Invoice"
            else:
                ref_doctype = "Purchase Invoice"
            
            # Validate invoice exists
            if not frappe.db.exists(ref_doctype, invoice_name):
                return {
                    "status": "error",
                    "message": f"{ref_doctype} '{invoice_name}' not found"
                }
            
            # Get invoice details
            inv = frappe.get_doc(ref_doctype, invoice_name)
            
            if inv.docstatus != 1:
                return {
                    "status": "error",
                    "message": f"{ref_doctype} '{invoice_name}' is not submitted"
                }
            
            # Add reference
            pe.append("references", {
                "reference_doctype": ref_doctype,
                "reference_name": invoice_name,
                "total_amount": inv.grand_total,
                "outstanding_amount": inv.outstanding_amount,
                "allocated_amount": allocated_amount,
                "exchange_rate": 1
            })
            
            total_allocated += allocated_amount
        
        # Validate total allocated amount
        if total_allocated > flt(data.get("paid_amount")):
            return {
                "status": "error",
                "message": f"Total allocated amount ({total_allocated}) exceeds paid amount ({data.get('paid_amount')})"
            }
        
        # Insert payment entry
        pe.insert(ignore_permissions=True)
        
        # Submit if requested
        if data.get("submit", False):
            pe.submit()
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Payment Entry '{pe.name}' created successfully",
            "data": {
                "payment_entry": pe.name,
                "party": pe.party,
                "paid_amount": pe.paid_amount,
                "total_allocated_amount": pe.total_allocated_amount,
                "unallocated_amount": pe.unallocated_amount,
                "docstatus": pe.docstatus,
                "status": "Draft" if pe.docstatus == 0 else "Submitted"
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Create Payment Entry API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_payment_entry():
    """
    API to submit a payment entry
    
    Method: POST
    URL: /api/method/your_app.api.submit_payment_entry
    Content-Type: application/json
    
    Body:
    {
        "payment_entry": "PE-00001"
    }
    
    Returns:
        JSON with submission status
    """
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        payment_entry_name = data.get("payment_entry")
        
        if not payment_entry_name:
            return {
                "status": "error",
                "message": "payment_entry is required"
            }
        
        if not frappe.db.exists("Payment Entry", payment_entry_name):
            return {
                "status": "error",
                "message": f"Payment Entry '{payment_entry_name}' not found"
            }
        
        pe = frappe.get_doc("Payment Entry", payment_entry_name)
        
        if pe.docstatus == 1:
            return {
                "status": "error",
                "message": "Payment Entry is already submitted"
            }
        
        if pe.docstatus == 2:
            return {
                "status": "error",
                "message": "Payment Entry is cancelled"
            }
        
        pe.submit()
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Payment Entry '{pe.name}' submitted successfully",
            "data": {
                "payment_entry": pe.name,
                "docstatus": pe.docstatus
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Submit Payment Entry Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


# ==================== ACCOUNTS RECEIVABLE APIs ====================

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_accounts_receivable_summary():
    """
    API to get accounts receivable summary for all customers or specific customer
    
    Method: GET
    URL: /api/method/your_app.api.get_accounts_receivable_summary
    
    Query Parameters:
    - customer: Filter by specific customer (optional)
    - company: Company name (optional, uses default if not provided)
    - as_on_date: Date to calculate receivables (default: today)
    - ageing_based_on: posting_date or due_date (default: posting_date)
    - range1: First ageing range (default: 30)
    - range2: Second ageing range (default: 60)
    - range3: Third ageing range (default: 90)
    - limit: Number of customers per page (default: 20)
    - offset: Starting position (default: 0)
    
    Returns:
        JSON with accounts receivable summary
    """
    try:
        filters = {}
        
        customer = frappe.form_dict.get("customer")
        if customer:
            filters["party"] = customer
        
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")
        as_on_date = frappe.form_dict.get("as_on_date", nowdate())
        ageing_based_on = frappe.form_dict.get("ageing_based_on", "posting_date")
        
        # Ageing ranges
        range1 = cint(frappe.form_dict.get("range1", 30))
        range2 = cint(frappe.form_dict.get("range2", 60))
        range3 = cint(frappe.form_dict.get("range3", 90))
        
        # Pagination
        limit = cint(frappe.form_dict.get("limit", 20))
        offset = cint(frappe.form_dict.get("offset", 0))
        
        # Get all outstanding invoices
        outstanding_invoices = frappe.db.sql("""
            SELECT 
                si.customer as party,
                si.customer_name as party_name,
                si.name as voucher_no,
                si.posting_date,
                si.due_date,
                si.grand_total,
                si.outstanding_amount,
                DATEDIFF(%s, {date_field}) as age_days,
                si.company,
                si.currency
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
            AND si.outstanding_amount > 0
            AND si.company = %s
            {customer_filter}
            ORDER BY si.posting_date DESC
        """.format(
            date_field=ageing_based_on,
            customer_filter="AND si.customer = %(customer)s" if customer else ""
        ), {
            "as_on_date": as_on_date,
            "company": company,
            "customer": customer
        }, as_dict=True)
        
        # Group by customer and calculate ageing
        customer_summary = {}
        
        for inv in outstanding_invoices:
            party = inv.party
            
            if party not in customer_summary:
                customer_summary[party] = {
                    "customer": party,
                    "customer_name": inv.party_name,
                    "currency": inv.currency,
                    "total_outstanding": 0,
                    f"range_0_{range1}": 0,
                    f"range_{range1}_{range2}": 0,
                    f"range_{range2}_{range3}": 0,
                    f"range_above_{range3}": 0,
                    "invoices": []
                }
            
            outstanding = flt(inv.outstanding_amount)
            age_days = inv.age_days or 0
            
            customer_summary[party]["total_outstanding"] += outstanding
            
            # Categorize by age
            if age_days <= range1:
                customer_summary[party][f"range_0_{range1}"] += outstanding
            elif age_days <= range2:
                customer_summary[party][f"range_{range1}_{range2}"] += outstanding
            elif age_days <= range3:
                customer_summary[party][f"range_{range2}_{range3}"] += outstanding
            else:
                customer_summary[party][f"range_above_{range3}"] += outstanding
            
            customer_summary[party]["invoices"].append({
                "invoice_no": inv.voucher_no,
                "posting_date": str(inv.posting_date),
                "due_date": str(inv.due_date),
                "grand_total": inv.grand_total,
                "outstanding_amount": outstanding,
                "age_days": age_days
            })
        
        # Convert to list and apply pagination
        customer_list = list(customer_summary.values())
        total_count = len(customer_list)
        
        # Sort by total outstanding (descending)
        customer_list.sort(key=lambda x: x["total_outstanding"], reverse=True)
        
        # Apply pagination
        paginated_list = customer_list[offset:offset + limit]
        
        # Calculate totals
        grand_total = sum(c["total_outstanding"] for c in customer_list)
        
        return {
            "status": "success",
            "count": len(paginated_list),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "summary": {
                "as_on_date": as_on_date,
                "company": company,
                "total_outstanding": grand_total,
                "ageing_based_on": ageing_based_on,
                "ranges": {
                    f"0-{range1} days": sum(c[f"range_0_{range1}"] for c in customer_list),
                    f"{range1}-{range2} days": sum(c[f"range_{range1}_{range2}"] for c in customer_list),
                    f"{range2}-{range3} days": sum(c[f"range_{range2}_{range3}"] for c in customer_list),
                    f"Above {range3} days": sum(c[f"range_above_{range3}"] for c in customer_list)
                }
            },
            "data": paginated_list
        }
        
    except Exception as e:
        frappe.log_error("Get Accounts Receivable Summary Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_receivable_details():
    """
    API to get detailed accounts receivable for a specific customer
    
    Method: GET
    URL: /api/method/your_app.api.get_customer_receivable_details?customer=CUST-001
    
    Query Parameters:
    - customer: Customer name (required)
    - company: Company name (optional)
    - as_on_date: Date to calculate receivables (default: today)
    - include_payments: Include payment history (default: true)
    
    Returns:
        JSON with detailed customer receivable information
    """
    try:
        customer = frappe.form_dict.get("customer")
        
        if not customer:
            return {
                "status": "error",
                "message": "customer is required"
            }
        
        if not frappe.db.exists("Customer", customer):
            return {
                "status": "error",
                "message": f"Customer '{customer}' not found"
            }
        
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")
        as_on_date = frappe.form_dict.get("as_on_date", nowdate())
        include_payments = frappe.form_dict.get("include_payments", "true").lower() == "true"
        
        # Get customer details
        customer_doc = frappe.get_doc("Customer", customer)
        
        # Get outstanding invoices
        outstanding_invoices = frappe.db.sql("""
            SELECT 
                name,
                posting_date,
                due_date,
                grand_total,
                outstanding_amount,
                DATEDIFF(%s, posting_date) as age_days,
                status
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND customer = %s
            AND company = %s
            AND outstanding_amount > 0
            ORDER BY posting_date DESC
        """, (as_on_date, customer, company), as_dict=True)
        
        total_outstanding = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices)
        
        # Get payment history if requested
        payment_history = []
        if include_payments:
            payments = frappe.db.sql("""
                SELECT 
                    pe.name,
                    pe.posting_date,
                    pe.paid_amount,
                    pe.mode_of_payment,
                    pe.reference_no,
                    pe.remarks
                FROM `tabPayment Entry` pe
                WHERE pe.docstatus = 1
                AND pe.party_type = 'Customer'
                AND pe.party = %s
                AND pe.company = %s
                AND pe.payment_type = 'Receive'
                ORDER BY pe.posting_date DESC
                LIMIT 10
            """, (customer, company), as_dict=True)
            
            for payment in payments:
                # Get invoice references
                refs = frappe.db.sql("""
                    SELECT reference_name, allocated_amount
                    FROM `tabPayment Entry Reference`
                    WHERE parent = %s
                """, payment.name, as_dict=True)
                
                payment["references"] = refs
                payment_history.append(payment)
        
        # Get all invoices (including paid)
        all_invoices = frappe.db.sql("""
            SELECT 
                name,
                posting_date,
                due_date,
                grand_total,
                outstanding_amount,
                paid_amount,
                status
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND customer = %s
            AND company = %s
            ORDER BY posting_date DESC
            LIMIT 50
        """, (customer, company), as_dict=True)
        
        total_invoiced = sum(flt(inv.grand_total) for inv in all_invoices)
        total_paid = sum(flt(inv.paid_amount) for inv in all_invoices)
        
        return {
            "status": "success",
            "data": {
                "customer": customer,
                "customer_name": customer_doc.customer_name,
                "customer_group": customer_doc.customer_group,
                "territory": customer_doc.territory,
                "tax_id": customer_doc.tax_id,
                "credit_limit": customer_doc.credit_limits[0].credit_limit if customer_doc.credit_limits else 0,
                
                "summary": {
                    "as_on_date": as_on_date,
                    "total_invoiced": total_invoiced,
                    "total_paid": total_paid,
                    "total_outstanding": total_outstanding,
                    "outstanding_count": len(outstanding_invoices)
                },
                
                "outstanding_invoices": [
                    {
                        "invoice_no": inv.name,
                        "posting_date": str(inv.posting_date),
                        "due_date": str(inv.due_date),
                        "grand_total": inv.grand_total,
                        "outstanding_amount": inv.outstanding_amount,
                        "age_days": inv.age_days,
                        "status": inv.status
                    }
                    for inv in outstanding_invoices
                ],
                
                "payment_history": [
                    {
                        "payment_entry": p.name,
                        "posting_date": str(p.posting_date),
                        "paid_amount": p.paid_amount,
                        "mode_of_payment": p.mode_of_payment,
                        "reference_no": p.reference_no,
                        "remarks": p.remarks,
                        "invoices_paid": [
                            {
                                "invoice_no": r.reference_name,
                                "allocated_amount": r.allocated_amount
                            }
                            for r in p.get("references", [])
                        ]
                    }
                    for p in payment_history
                ] if include_payments else [],
                
                "recent_invoices": [
                    {
                        "invoice_no": inv.name,
                        "posting_date": str(inv.posting_date),
                        "due_date": str(inv.due_date),
                        "grand_total": inv.grand_total,
                        "outstanding_amount": inv.outstanding_amount,
                        "paid_amount": inv.paid_amount,
                        "status": inv.status
                    }
                    for inv in all_invoices[:10]
                ]
            }
        }
        
    except Exception as e:
        frappe.log_error("Get Customer Receivable Details Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_outstanding_invoices_for_payment():
    """
    API to get outstanding invoices for a customer to create payment entry
    
    Method: GET
    URL: /api/method/your_app.api.get_outstanding_invoices_for_payment?customer=CUST-001
    
    Query Parameters:
    - customer: Customer name (required)
    - company: Company name (optional)
    
    Returns:
        JSON with list of outstanding invoices ready for payment allocation
    """
    try:
        customer = frappe.form_dict.get("customer")
        
        if not customer:
            return {
                "status": "error",
                "message": "customer is required"
            }
        
        if not frappe.db.exists("Customer", customer):
            return {
                "status": "error",
                "message": f"Customer '{customer}' not found"
            }
        
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")
        
        # Get outstanding invoices
        invoices = frappe.db.sql("""
            SELECT 
                name as invoice_no,
                posting_date,
                due_date,
                grand_total,
                outstanding_amount,
                DATEDIFF(CURDATE(), due_date) as overdue_days,
                currency
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND customer = %s
            AND company = %s
            AND outstanding_amount > 0
            ORDER BY posting_date ASC
        """, (customer, company), as_dict=True)
        
        total_outstanding = sum(flt(inv.outstanding_amount) for inv in invoices)
        
        return {
            "status": "success",
            "count": len(invoices),
            "summary": {
                "customer": customer,
                "total_outstanding": total_outstanding,
                "invoice_count": len(invoices),
                "overdue_count": sum(1 for inv in invoices if inv.overdue_days > 0)
            },
            "data": [
                {
                    "invoice_no": inv.invoice_no,
                    "posting_date": str(inv.posting_date),
                    "due_date": str(inv.due_date),
                    "grand_total": inv.grand_total,
                    "outstanding_amount": inv.outstanding_amount,
                    "overdue_days": inv.overdue_days,
                    "is_overdue": inv.overdue_days > 0,
                    "currency": inv.currency
                }
                for inv in invoices
            ]
        }
        
    except Exception as e:
        frappe.log_error("Get Outstanding Invoices Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }