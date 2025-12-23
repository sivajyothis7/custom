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
import frappe
import json
from frappe.utils import getdate, flt, cint, nowdate
from frappe import _

def is_accounts_user():
    """Check if current user has Role Profile = Accounts"""
    user = frappe.get_doc("User", frappe.session.user)
    return user.role_profile_name == "Accounts"


def get_user_warehouse():
    """
    Get warehouse linked via User Permission for Accounts users
    """
    warehouse = frappe.db.get_value(
        "User Permission",
        {
            "user": frappe.session.user,
            "allow": "Warehouse"
        },
        "for_value"
    )

    if not warehouse:
        frappe.throw(_("No Warehouse User Permission found for this user"))

    return warehouse


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
        
        try:
            frappe.auth.check_password(email, password)
        except frappe.exceptions.AuthenticationError:
            return {
                "status": "error",
                "message": "Invalid email or password"
            }
        
        user = frappe.get_doc("User", email)
        
        if user.enabled == 0:
            return {
                "status": "error",
                "message": "User account is disabled"
            }
        
        api_key = user.api_key
        api_secret = None
        
        if not api_key:
            api_key = frappe.generate_hash(length=15)
            api_secret = frappe.generate_hash(length=15)
            
            user.api_key = api_key
            user.api_secret = api_secret
            user.save(ignore_permissions=True)
            frappe.db.commit()
        else:
            api_secret = user.get_password('api_secret')
        
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
                "expires_in": 86400 
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
    
    frappe.cache().set_value(
        f"auth_token:{token}",
        {
            "user": user_email,
            "expiry": expiry.isoformat()
        },
        expires_in_sec=86400  
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



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_items_list():
    """
    API to list all items with filtering and pagination
    """

    try:
        filters = {}

        customer = frappe.form_dict.get("customer")

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

        search = frappe.form_dict.get("search")
        if search:
            filters["item_code"] = ["like", f"%{search}%"]

        limit = cint(frappe.form_dict.get("limit", 20))
        offset = cint(frappe.form_dict.get("offset", 0))

        order_by = frappe.form_dict.get("order_by", "item_name")
        order = frappe.form_dict.get("order", "asc")

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

        # -------------------------------
        # RATE RESOLUTION (Nos / Carton)
        # -------------------------------
        for item in items:
            rates = {
                "Nos": 0,
                "Carton": 0
            }

            for uom in ["Nos", "Carton"]:
                rate = None

                # 1️⃣ Last rate for this customer
                if customer:
                    rate = frappe.db.sql("""
                        SELECT sii.rate
                        FROM `tabSales Invoice Item` sii
                        INNER JOIN `tabSales Invoice` si
                            ON si.name = sii.parent
                        WHERE
                            si.customer = %s
                            AND sii.item_code = %s
                            AND sii.uom = %s
                            AND si.docstatus = 1
                        ORDER BY si.posting_date DESC, si.creation DESC
                        LIMIT 1
                    """, (customer, item["item_code"], uom))

                    rate = rate[0][0] if rate else None

                # 2️⃣ Fallback: Standard Selling Price List
                if rate is None:
                    rate = frappe.db.get_value(
                        "Item Price",
                        {
                            "item_code": item["item_code"],
                            "uom": uom,
                            "selling": 1
                        },
                        "price_list_rate"
                    )

                rates[uom] = flt(rate or 0)

            # attach rates without breaking structure
            item["rates"] = rates

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
    """

    try:
        item_code = frappe.form_dict.get("item_code")
        customer = frappe.form_dict.get("customer")  # optional

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

        # ------------------------------------------------
        # USER + WAREHOUSE CONTEXT (Accounts only)
        # ------------------------------------------------
        user = frappe.get_doc("User", frappe.session.user)
        user_warehouse = None

        if user.role_profile_name == "Accounts":
            user_warehouse = frappe.db.get_value(
                "User Permission",
                {
                    "user": frappe.session.user,
                    "allow": "Warehouse"
                },
                "for_value"
            )

            if not user_warehouse:
                frappe.throw("No Warehouse User Permission found for this user")

        # ------------------------------------------------
        # UOM CONVERSIONS
        # ------------------------------------------------
        uom_conversions = [
            {
                "uom": u.uom,
                "conversion_factor": u.conversion_factor
            }
            for u in item.uoms
        ]

        # ------------------------------------------------
        # STOCK LEVELS (WAREHOUSE RESTRICTED)
        # ------------------------------------------------
        stock_filters = {"item_code": item_code}
        if user_warehouse:
            stock_filters["warehouse"] = user_warehouse

        stock_levels = []
        if item.is_stock_item:
            stock_levels = frappe.get_all(
                "Bin",
                filters=stock_filters,
                fields=[
                    "warehouse",
                    "actual_qty",
                    "reserved_qty",
                    "ordered_qty",
                    "projected_qty"
                ]
            )

        # ------------------------------------------------
        # PRICE FILTER (STANDARD SELLING ONLY)
        # ------------------------------------------------
        price_filters = {
            "item_code": item_code,
            "selling": 1,
            "price_list": "Standard Selling"
        }

        if customer:
            price_filters["customer"] = ["in", [customer, None]]
        else:
            price_filters["customer"] = ["is", "not set"]

        # ------------------------------------------------
        # ITEM PRICES (LATEST FIRST – REFERENCE)
        # ------------------------------------------------
        item_prices = frappe.get_all(
            "Item Price",
            filters=price_filters,
            fields=[
                "price_list",
                "price_list_rate",
                "currency",
                "uom",
                "customer",
                "valid_from",
                "valid_upto",
                "modified"
            ],
            order_by="modified desc, creation desc"
        )

        # ------------------------------------------------
        # RATES (Nos / Carton) – LATEST STANDARD SELLING
        # ------------------------------------------------
        rates = {"Nos": 0, "Carton": 0}

        for uom in ["Nos", "Carton"]:
            rate = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item_code,
                    "uom": uom,
                    "selling": 1,
                    "price_list": "Standard Selling",
                    "customer": ["in", [customer, None]]
                },
                "price_list_rate",
                order_by="modified desc, creation desc"
            )

            rates[uom] = flt(rate or 0)

        # ------------------------------------------------
        # STANDARD RATE (LATEST STANDARD SELLING – NOS)
        # ------------------------------------------------
        standard_rate = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "uom": item.stock_uom,
                "selling": 1,
                "price_list": "Standard Selling",
                "customer": ["in", [customer, None]]
            },
            "price_list_rate",
            order_by="modified desc, creation desc"
        )

        standard_rate = flt(standard_rate or item.standard_rate)

        # ------------------------------------------------
        # RESPONSE
        # ------------------------------------------------
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
                "standard_rate": standard_rate,
                "image": item.image,
                "disabled": item.disabled,
                "has_variants": item.has_variants,
                "variant_of": item.variant_of,

                "rates": rates,

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
    API: Customers list with calculated outstanding balance

    Show customers where:
    - User is Sales Person
    - OR Sales Person is completely blank

    Outstanding:
    - ONLY for invoices created by the logged-in user
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

        # -------------------------------------------------
        # LOGGED-IN CONTEXT
        # -------------------------------------------------
        current_user = frappe.session.user

        sales_person = frappe.db.get_value(
            "Sales Person",
            {"user": current_user},
            "name"
        )

        # -------------------------------------------------
        # FETCH BASE CUSTOMER LIST
        # -------------------------------------------------
        customers = frappe.get_all(
            "Customer",
            filters=filters,
            fields=[
                "name",
                "customer_name",
                "custom_customer_name_english",
                "customer_type",
                "customer_group",
                "territory",
                "tax_id",
                "disabled",
                "creation",
                "modified"
            ],
            order_by="custom_customer_name_english asc"
        )

        result = []

        # -------------------------------------------------
        # APPLY SALES PERSON VISIBILITY + OUTSTANDING LOGIC
        # -------------------------------------------------
        for cust in customers:

            sales_team = frappe.get_all(
                "Sales Team",
                filters={"parent": cust["name"]},
                fields=["sales_person"]
            )

            # -------------------------
            # VISIBILITY CHECK
            # -------------------------
            if not sales_team:
                # No sales person assigned → include
                include_customer = True
            else:
                # Include only if logged-in user's sales person is present
                include_customer = bool(
                    sales_person and
                    any(st.sales_person == sales_person for st in sales_team)
                )

            if not include_customer:
                continue

            # -------------------------
            # OUTSTANDING (USER-CREATED ONLY)
            # -------------------------
            outstanding = frappe.db.sql("""
                SELECT SUM(outstanding_amount)
                FROM `tabSales Invoice`
                WHERE customer = %s
                  AND owner = %s
                  AND docstatus = 1
            """, (cust["name"], current_user))[0][0]

            cust["outstanding_amount"] = flt(outstanding or 0)

            result.append(cust)

        return {
            "status": "success",
            "count": len(result),
            "data": result
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


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_customer_address():
    """
    Create Address for Customer according to custom mandatory fields.

    Required Fields:
    - customer
    - address_title
    - address_line1
    - custom_building_number
    - custom_area
    - country
    - pincode
    """

    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict

        # -------------------------
        # REQUIRED FIELDS
        # -------------------------
        customer = data.get("customer")
        address_title = data.get("address_title")
        address_line1 = data.get("address_line1")
        building = data.get("custom_building_number")
        area = data.get("custom_area")
        country = data.get("country")
        pincode = data.get("pincode")

        # -------------------------
        # VALIDATION
        # -------------------------
        if not customer:
            return {"status": "error", "message": "customer is required"}

        if not frappe.db.exists("Customer", customer):
            return {"status": "error", "message": f"Customer '{customer}' not found"}

        missing = []
        if not address_title: missing.append("address_title")
        if not address_line1: missing.append("address_line1")
        if not building: missing.append("custom_building_number")
        if not area: missing.append("custom_area")
        if not country: missing.append("country")
        if not pincode: missing.append("pincode")

        if missing:
            return {
                "status": "error",
                "message": "Missing mandatory fields",
                "missing": missing
            }

        # -------------------------
        # CREATE ADDRESS DOC
        # -------------------------
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": address_title,
            "address_type": data.get("address_type", "Billing"),

            "address_line1": address_line1,
            "custom_building_number": building,
            "custom_area": area,
            "city": data.get("city"),          # Optional
            "state": data.get("state"),        # Optional
            "country": country,
            "pincode": pincode,

            "phone": data.get("phone"),
            "email_id": data.get("email_id"),

            "is_primary_address": cint(data.get("is_primary_address", 0)),
            "is_shipping_address": cint(data.get("is_shipping_address", 0)),
            "disabled": cint(data.get("disabled", 0)),

            # ✅ LINK TO CUSTOMER
            "links": [
                {
                    "link_doctype": "Customer",
                    "link_name": customer
                }
            ]
        })

        address.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Customer address created",
            "data": {
                "address_name": address.name,
                "customer": customer,
                "address_title": address.address_title
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Create Customer Address Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["POST"])
def update_customer_address():
    """
    Update an existing Address.
    Customer must be passed from API URL (?customer=XXXX).

    Required:
    - customer (from URL)
    - address_name (in JSON body)

    Only provided fields will be updated.
    """

    try:
        # -----------------------------
        # READ JSON BODY PROPERLY
        # -----------------------------
        body = {}
        if frappe.request.data:
            try:
                body = json.loads(frappe.request.data)
            except:
                body = frappe.form_dict

        # -----------------------------
        # GET CUSTOMER FROM URL
        # -----------------------------
        customer = frappe.form_dict.get("customer")
        if not customer:
            return {"status": "error", "message": "customer is required in the API URL"}

        if not frappe.db.exists("Customer", customer):
            return {"status": "error", "message": f"Customer '{customer}' not found"}

        # -----------------------------
        # ADDRESS NAME (FROM BODY)
        # -----------------------------
        address_name = body.get("address_name")
        if not address_name:
            return {"status": "error", "message": "address_name is required"}

        if not frappe.db.exists("Address", address_name):
            return {"status": "error", "message": f"Address '{address_name}' not found"}

        # Load document
        doc = frappe.get_doc("Address", address_name)

        # -----------------------------
        # UPDATE ADDRESS FIELDS
        # Only update fields if provided
        # -----------------------------
        editable_fields = [
            "address_title", "address_type", "address_line1", "address_line2",
            "custom_building_number", "custom_area",
            "city", "state", "country", "pincode",
            "phone", "email_id",
            "is_primary_address", "is_shipping_address", "disabled"
        ]

        for field in editable_fields:
            if field in body:
                doc.set(field, body.get(field))

        # -----------------------------
        # LINK ADDRESS TO CUSTOMER
        # Always ensures correct link
        # -----------------------------
        frappe.db.delete(
            "Dynamic Link",
            {"parent": address_name, "link_doctype": "Customer"}
        )

        doc.append("links", {
            "link_doctype": "Customer",
            "link_name": customer
        })

        # -----------------------------
        # SAVE
        # -----------------------------
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Address '{address_name}' updated successfully",
            "data": {
                "address_name": address_name,
                "customer": customer
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error("Update Customer Address Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}




@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_with_addresses():
    """
    Returns customer details first, then all addresses linked to the customer.

    Query Parameters:
    - customer (required)
    """

    try:
        customer = frappe.form_dict.get("customer")
        if not customer:
            return {"status": "error", "message": "customer is required"}

        # Validate customer
        if not frappe.db.exists("Customer", customer):
            return {"status": "error", "message": f"Customer '{customer}' not found"}

        # ----------------------------
        # CUSTOMER DETAILS
        # ----------------------------
        cust = frappe.get_doc("Customer", customer)

        customer_details = {
            "customer_id": cust.name,
            "customer_name": cust.customer_name,
            "customer_type": cust.customer_type,
            "customer_group": cust.customer_group,
            "territory": cust.territory,
            "tax_id": cust.tax_id,
            "mobile_no": cust.mobile_no,
            "email_id": cust.email_id
        }

        # ----------------------------
        # FIND ALL ADDRESSES LINKED TO CUSTOMER
        # ----------------------------
        address_links = frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": customer},
            fields=["parent as address_name"]
        )

        if not address_links:
            return {
                "status": "success",
                "customer": customer_details,
                "addresses": []
            }

        address_names = [a.address_name for a in address_links]

        # ----------------------------
        # FETCH ADDRESS DETAILS
        # ----------------------------
        addresses = frappe.get_all(
            "Address",
            filters={"name": ["in", address_names]},
            fields=[
                "name",
                "address_title",
                "address_type",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "country",
                "pincode",
                "phone",
                "email_id",
                "custom_building_number",
                "custom_area",
                "is_primary_address",
                "is_shipping_address",
                "modified"
            ],
            order_by="is_primary_address desc, modified desc"
        )

        return {
            "status": "success",
            "customer": customer_details,
            "addresses": addresses,
            "count": len(addresses)
        }

    except Exception as e:
        frappe.log_error("Customer With Address Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}






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

@frappe.whitelist(allow_guest=True)
def get_sales_invoice_list():
    """
    Fetch Sales Invoice list with DIRECT PDF download URL
    Print Format: Sales Invoice PF
    """

    customer = frappe.form_dict.get("customer")
    status = frappe.form_dict.get("status")
    start_date = frappe.form_dict.get("start_date")
    end_date = frappe.form_dict.get("end_date")

    filters = {}

    if customer:
        filters["customer"] = customer

    if status:
        filters["status"] = status

    if start_date and end_date:
        filters["posting_date"] = ["between", [start_date, end_date]]

    # 🔐 ADDITION: Accounts users see invoices only for their warehouse
    user = frappe.get_doc("User", frappe.session.user)
    if user.role_profile_name == "Accounts":
        user_warehouse = frappe.db.get_value(
            "User Permission",
            {
                "user": frappe.session.user,
                "allow": "Warehouse"
            },
            "for_value"
        )

        if not user_warehouse:
            frappe.throw("No Warehouse User Permission found for this user")

        filters["set_warehouse"] = user_warehouse

    invoice_names = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=["name"],
        order_by="posting_date desc, modified desc"
    )

    base_url = frappe.utils.get_url()
    invoice_list = []

    # ✅ Encode the format safely
    print_format = frappe.utils.quote("Sales Invoice PF OG")

    for inv in invoice_names:
        doc = frappe.get_doc("Sales Invoice", inv.name)

        # ✅ DIRECT DOWNLOAD PDF URL
        pdf_url = (
            f"{base_url}/api/method/frappe.utils.print_format.download_pdf?"
            f"doctype=Sales%20Invoice"
            f"&name={doc.name}"
            f"&format={print_format}"
            f"&no_letterhead=0"
            f"&download=1"
        )

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
            "status": doc.status,

            # ✅ PDF file download link
            "pdf_url": pdf_url
        })

    return {
        "status_code": 200,
        "print_format": "Sales Invoice PF",
        "count": len(invoice_list),
        "invoices": invoice_list
    }



@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_sales_invoice():
    """
    Create or update a Sales Invoice with:
    - Item creation
    - Default tax template auto-detected
    - Manual fallback disabled
    - Stock update
    - VAT summary
    - Custom Mode of Payment
    - Discount (Amount / Percentage)
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

        # Ensure customer
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

        # 🔐 FORCE WAREHOUSE FOR ACCOUNTS USERS
        user = frappe.get_doc("User", frappe.session.user)
        if user.role_profile_name == "Accounts":
            target_warehouse = frappe.db.get_value(
                "User Permission",
                {
                    "user": frappe.session.user,
                    "allow": "Warehouse"
                },
                "for_value"
            )

            if not target_warehouse:
                frappe.throw("No Warehouse User Permission found for this user")
        else:
            target_warehouse = data.get("target_warehouse") or get_default_warehouse(company)

        custom_mode_of_payment = data.get("custom_mode_of_payment")

        if custom_mode_of_payment and not frappe.db.exists("Mode of Payment", custom_mode_of_payment):
            return {
                "status": "error",
                "message": f"Mode of Payment '{custom_mode_of_payment}' not found"
            }

        # ---------------------------
        # BUILD ITEMS
        # ---------------------------
        invoice_items = []

        for item in data.get("items"):
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

            # 🔐 FORCE ITEM WAREHOUSE
            if update_stock and target_warehouse:
                row["warehouse"] = target_warehouse

            invoice_items.append(row)

        # ---------------------------
        # DEFAULT TAX TEMPLATE
        # ---------------------------
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
                "message": f"No default Sales Taxes and Charges Template for '{company}'"
            }

        tpl = frappe.get_doc("Sales Taxes and Charges Template", resolved_tax_template)
        tax_rows = [{
            "charge_type": t.charge_type,
            "account_head": t.account_head,
            "description": t.description,
            "rate": t.rate,
            "cost_center": cost_center
        } for t in tpl.taxes]

        invoice_name = data.get("invoice_name")

        # ---------------------------
        # CREATE / UPDATE
        # ---------------------------
        if invoice_name and frappe.db.exists("Sales Invoice", invoice_name):
            doc = frappe.get_doc("Sales Invoice", invoice_name)

            if doc.docstatus != 0:
                return {"status": "error", "message": "Invoice submitted; cannot update"}

            doc.customer = customer_name
            doc.company = company
            doc.posting_date = posting_date
            doc.due_date = due_date
            doc.items = invoice_items
            doc.taxes = tax_rows
            doc.taxes_and_charges = resolved_tax_template
            doc.update_stock = update_stock

            if target_warehouse:
                doc.set_warehouse = target_warehouse

            if custom_mode_of_payment:
                doc.custom_mode_of_payment = custom_mode_of_payment

        else:
            doc = frappe.get_doc({
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
                "taxes_and_charges": resolved_tax_template,
                "custom_mode_of_payment": custom_mode_of_payment,
                "set_warehouse": target_warehouse
            })

            if data.get("naming_series"):
                doc.naming_series = data["naming_series"]

        # ---------------------------
        # APPLY DISCOUNT ✅
        # ---------------------------
        if data.get("discount_amount"):
            doc.discount_amount = flt(data.get("discount_amount"))
            doc.apply_discount_on = data.get("apply_discount_on", "Grand Total")

        if data.get("discount_percentage"):
            doc.additional_discount_percentage = flt(data.get("discount_percentage"))
            doc.apply_discount_on = data.get("apply_discount_on", "Grand Total")

        doc.insert(ignore_permissions=True) if not doc.name else doc.save(ignore_permissions=True)
        frappe.db.commit()

        # ---------------------------
        # RESPONSE
        # ---------------------------
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
                "discount_amount": doc.discount_amount or 0,
                "discount_percentage": doc.additional_discount_percentage or 0,
                "apply_discount_on": doc.apply_discount_on or "",

                "vat_amount": doc.total_taxes_and_charges,
                "tax_total": doc.total_taxes_and_charges,
                "grand_total": doc.grand_total,
                "rounded_total": doc.rounded_total or doc.grand_total,
                "rounding_adjustment": doc.rounding_adjustment or 0,
                "outstanding_amount": doc.outstanding_amount,

                "custom_mode_of_payment": doc.custom_mode_of_payment,

                "items": [{
                    "item_code": i.item_code,
                    "qty": i.qty,
                    "rate": i.rate,
                    "amount": i.amount,
                    "uom": i.uom,
                    "description": i.description
                } for i in doc.items],

                "taxes": [{
                    "description": t.description,
                    "charge_type": t.charge_type,
                    "account_head": t.account_head,
                    "cost_center": t.cost_center,
                    "rate": t.rate,
                    "tax_amount": t.tax_amount
                } for t in doc.taxes]
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Sales Invoice API Error")
        return {"status": "error", "message": str(e)}



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_invoice_details():
    """
    API to get Sales Invoice details with direct PDF download link
    Print Format: Sales Invoice PF
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

       
        base_url = frappe.utils.get_url()
        print_format = frappe.utils.quote("Sales Invoice PF")

        pdf_url = (
            f"{base_url}/api/method/frappe.utils.print_format.download_pdf?"
            f"doctype=Sales%20Invoice"
            f"&name={doc.name}"
            f"&format={print_format}"
            f"&no_letterhead=0"
            f"&download=1"
        )

      
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
                "taxes": taxes,

                "pdf_url": pdf_url
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







@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_payment_entries_list():
    """
    API to list payment entries.
    Draft and Submitted included.
    Cancelled excluded.
    Latest entries appear first.
    """

    try:
        filters = {
            "docstatus": ["!=", 2]   # ✅ Exclude Cancelled only
        }

        party = frappe.form_dict.get("party")
        if party:
            filters["party"] = party

        party_type = frappe.form_dict.get("party_type", "Customer")
        filters["party_type"] = party_type

        payment_type = frappe.form_dict.get("payment_type")
        if payment_type:
            filters["payment_type"] = payment_type

        mode_of_payment = frappe.form_dict.get("mode_of_payment")
        if mode_of_payment:
            filters["mode_of_payment"] = mode_of_payment

        from_date = frappe.form_dict.get("from_date")
        to_date = frappe.form_dict.get("to_date")

        if from_date and to_date:
            filters["posting_date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["posting_date"] = [">=", from_date]
        elif to_date:
            filters["posting_date"] = ["<=", to_date]

        order_by = frappe.form_dict.get("order_by", "posting_date")
        order = frappe.form_dict.get("order", "desc")

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
                "creation",
                "modified",
                "company"
            ],
            order_by=f"{order_by} {order}, modified desc"
        )

        return {
            "status": "success",
            "total": len(payment_entries),
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
        
        if not frappe.db.exists(party_type, party):
            return {
                "status": "error",
                "message": f"{party_type} '{party}' not found"
            }
        
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
        
        invoices = data.get("invoices", [])
        total_allocated = 0
        
        for inv_data in invoices:
            invoice_name = inv_data.get("reference_name")
            allocated_amount = flt(inv_data.get("allocated_amount", 0))
            
            if not invoice_name:
                continue
            
            if payment_type == "Receive":
                ref_doctype = "Sales Invoice"
            else:
                ref_doctype = "Purchase Invoice"
            
            if not frappe.db.exists(ref_doctype, invoice_name):
                return {
                    "status": "error",
                    "message": f"{ref_doctype} '{invoice_name}' not found"
                }
            
            inv = frappe.get_doc(ref_doctype, invoice_name)
            
            if inv.docstatus != 1:
                return {
                    "status": "error",
                    "message": f"{ref_doctype} '{invoice_name}' is not submitted"
                }
            
            pe.append("references", {
                "reference_doctype": ref_doctype,
                "reference_name": invoice_name,
                "total_amount": inv.grand_total,
                "outstanding_amount": inv.outstanding_amount,
                "allocated_amount": allocated_amount,
                "exchange_rate": 1
            })
            
            total_allocated += allocated_amount
        
        if total_allocated > flt(data.get("paid_amount")):
            return {
                "status": "error",
                "message": f"Total allocated amount ({total_allocated}) exceeds paid amount ({data.get('paid_amount')})"
            }
        
        pe.insert(ignore_permissions=True)
        
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
        
        range1 = cint(frappe.form_dict.get("range1", 30))
        range2 = cint(frappe.form_dict.get("range2", 60))
        range3 = cint(frappe.form_dict.get("range3", 90))
        
        limit = cint(frappe.form_dict.get("limit", 20))
        offset = cint(frappe.form_dict.get("offset", 0))
        
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
        
        customer_list = list(customer_summary.values())
        total_count = len(customer_list)
        
        customer_list.sort(key=lambda x: x["total_outstanding"], reverse=True)
        
        paginated_list = customer_list[offset:offset + limit]
        
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
        
        customer_doc = frappe.get_doc("Customer", customer)
        
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
                refs = frappe.db.sql("""
                    SELECT reference_name, allocated_amount
                    FROM `tabPayment Entry Reference`
                    WHERE parent = %s
                """, payment.name, as_dict=True)
                
                payment["references"] = refs
                payment_history.append(payment)
        
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



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_billing_and_payments():
    """
    Combined API:
    - All Submitted Sales Invoices (including Paid)
    - Submitted Payment Entries
    
    Filters:
    - customer
    - from_date
    - to_date

    Returns:
    - Full ledger list (no pagination)
    - Total Billed
    - Total Paid
    - Total Outstanding
    """

    try:
        customer = frappe.form_dict.get("customer")
        from_date = frappe.form_dict.get("from_date")
        to_date = frappe.form_dict.get("to_date")

        date_filter = None
        if from_date and to_date:
            date_filter = ["between", [from_date, to_date]]
        elif from_date:
            date_filter = [">=", from_date]
        elif to_date:
            date_filter = ["<=", to_date]

        # --------------------------
        # SALES INVOICES
        # --------------------------
        inv_filters = {"docstatus": 1}

        if customer:
            inv_filters["customer"] = customer
        if date_filter:
            inv_filters["posting_date"] = date_filter

        invoices = frappe.get_all(
            "Sales Invoice",
            filters=inv_filters,
            fields=[
                "name", "posting_date", "customer",
                "grand_total", "outstanding_amount",
                "due_date", "status"
            ]
        )

        # --------------------------
        # PAYMENT ENTRIES
        # --------------------------
        pay_filters = {
            "party_type": "Customer",
            "docstatus": 1
        }

        if customer:
            pay_filters["party"] = customer
        if date_filter:
            pay_filters["posting_date"] = date_filter

        payments = frappe.get_all(
            "Payment Entry",
            filters=pay_filters,
            fields=[
                "name", "posting_date", "party",
                "paid_amount", "received_amount",
                "mode_of_payment", "payment_type"
            ]
        )

        # --------------------------
        # TOTALS
        # --------------------------
        total_billed = 0
        total_paid = 0
        total_outstanding = 0

        for inv in invoices:
            total_billed += flt(inv["grand_total"])
            total_outstanding += flt(inv["outstanding_amount"])
            total_paid += flt(inv["grand_total"]) - flt(inv["outstanding_amount"])

            inv["source"] = "Invoice"
            inv["amount"] = inv["grand_total"]
            inv["date"] = inv["posting_date"]
            inv["invoice_status"] = inv["status"]

        for pay in payments:
            paid = flt(pay["received_amount"] or pay["paid_amount"])
            total_paid += paid

            pay["source"] = "Payment"
            pay["customer"] = pay["party"]
            pay["amount"] = paid
            pay["date"] = pay["posting_date"]
            pay["invoice_status"] = None

        # --------------------------
        # FINAL COMBINED LIST
        # --------------------------
        combined = invoices + payments
        combined.sort(key=lambda x: x["date"], reverse=True)

        return {
            "status": "success",
            "filters": {
                "customer": customer,
                "from_date": from_date,
                "to_date": to_date
            },
            "summary": {
                "total_billed": total_billed,
                "total_paid": total_paid,
                "total_outstanding": total_outstanding
            },
            "total_records": len(combined),
            "data": combined
        }

    except Exception as e:
        frappe.log_error("Combined Billing API Error", frappe.get_traceback())
        return {
            "status": "error",
            "message": str(e)
        }



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_today_sales():
    """Today's sales invoice total"""

    try:
        today = frappe.utils.today()

        data = frappe.db.sql("""
            SELECT
                COUNT(name) as invoice_count,
                SUM(grand_total) as total_sales
            FROM `tabSales Invoice`
            WHERE
                posting_date = %s
                AND docstatus = 1
        """, today, as_dict=True)[0]

        return {
            "status": "success",
            "date": today,
            "amount": data.total_sales or 0,
            "invoices": data.invoice_count or 0
        }

    except Exception as e:
        frappe.log_error("Today Sales API Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_today_collection():
    """Today's total collection"""

    try:
        today = frappe.utils.today()

        data = frappe.db.sql("""
            SELECT
                COUNT(name) as payment_count,
                SUM(received_amount) as total_collection
            FROM `tabPayment Entry`
            WHERE
                posting_date = %s
                AND docstatus = 1
                AND payment_type = 'Receive'
        """, today, as_dict=True)[0]

        return {
            "status": "success",
            "date": today,
            "amount": data.total_collection or 0,
            "payments": data.payment_count or 0
        }

    except Exception as e:
        frappe.log_error("Today Collection API Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}





@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_today_cash_collection():
    """Today's CASH collection"""

    try:
        today = frappe.utils.today()

        data = frappe.db.sql("""
            SELECT
                COUNT(name) as payment_count,
                SUM(received_amount) as cash_collection
            FROM `tabPayment Entry`
            WHERE
                posting_date = %s
                AND docstatus = 1
                AND payment_type = 'Receive'
                AND mode_of_payment = 'Cash'
        """, today, as_dict=True)[0]

        return {
            "status": "success",
            "date": today,
            "amount": data.cash_collection or 0,
            "payments": data.payment_count or 0
        }

    except Exception as e:
        frappe.log_error("Cash Collection API Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}




@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_today_bank_collection():
    """Today's BANK collection"""

    try:
        today = frappe.utils.today()

        data = frappe.db.sql("""
            SELECT
                COUNT(name) as payment_count,
                SUM(received_amount) as bank_collection
            FROM `tabPayment Entry`
            WHERE
                posting_date = %s
                AND docstatus = 1
                AND payment_type = 'Receive'
                AND mode_of_payment = 'Bank Draft'
        """, today, as_dict=True)[0]

        return {
            "status": "success",
            "date": today,
            "amount": data.bank_collection or 0,
            "payments": data.payment_count or 0
        }

    except Exception as e:
        frappe.log_error("Bank Collection API Error", frappe.get_traceback())
        return {"status": "error", "message": str(e)}




import frappe
import json
from frappe.utils import getdate, flt, cint, nowdate
from frappe import _


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_sales_return():
    """
    Create a Sales Return (Credit Note) against a Sales Invoice.
    
    Two methods supported:
    1. Full return - Return entire invoice
    2. Partial return - Return specific items with quantities
    
    Features:
    - Auto-creates return invoice with negative quantities
    - Links to original invoice
    - Updates stock if original invoice updated stock
    - Preserves tax template and calculations
    - Supports custom return reasons
    """
    
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        # Required field
        original_invoice = data.get("original_invoice")
        if not original_invoice:
            return {"status": "error", "message": "original_invoice is required"}
        
        # Validate original invoice exists and is submitted
        if not frappe.db.exists("Sales Invoice", original_invoice):
            return {"status": "error", "message": f"Sales Invoice '{original_invoice}' not found"}
        
        original_doc = frappe.get_doc("Sales Invoice", original_invoice)
        
        if original_doc.docstatus != 1:
            return {
                "status": "error", 
                "message": f"Original invoice must be submitted. Current status: {original_doc.docstatus}"
            }
        
        # Check if invoice is already fully returned
        if original_doc.is_return:
            return {"status": "error", "message": "Cannot create return against a return invoice"}
        
        # Get return date
        posting_date = getdate(data.get("posting_date") or nowdate())
        
        # Validate posting date is not before original invoice date
        if posting_date < original_doc.posting_date:
            return {
                "status": "error",
                "message": f"Return date cannot be before original invoice date ({original_doc.posting_date})"
            }
        
        # Check if full return or partial return
        return_items = data.get("items")  # If provided, partial return
        custom_return_reason = data.get("custom_return_reason", "")
        
        # Create return invoice data
        return_invoice_data = {
            "doctype": "Sales Invoice",
            "customer": original_doc.customer,
            "company": original_doc.company,
            "posting_date": posting_date,
            "due_date": posting_date,
            "is_return": 1,
            "return_against": original_invoice,
            "currency": original_doc.currency,
            "debit_to": original_doc.debit_to,
            "update_stock": original_doc.update_stock,
            "conversion_rate": original_doc.conversion_rate,
            "taxes_and_charges": original_doc.taxes_and_charges,
            "items": [],
            "taxes": []
        }
        
        # Add naming series if provided
        if data.get("naming_series"):
            return_invoice_data["naming_series"] = data["naming_series"]
        
        # Add warehouse if stock update enabled
        if original_doc.update_stock and original_doc.set_warehouse:
            return_invoice_data["set_warehouse"] = original_doc.set_warehouse
        
        # Process items
        if return_items:
            # Partial return - specific items and quantities
            for return_item in return_items:
                item_code = return_item.get("item_code")
                return_qty = flt(return_item.get("qty", 0))
                
                if not item_code or return_qty <= 0:
                    continue
                
                # Find original item
                original_item = None
                for orig_item in original_doc.items:
                    if orig_item.item_code == item_code:
                        original_item = orig_item
                        break
                
                if not original_item:
                    return {
                        "status": "error",
                        "message": f"Item '{item_code}' not found in original invoice"
                    }
                
                # Validate return quantity
                if return_qty > original_item.qty:
                    return {
                        "status": "error",
                        "message": f"Return qty {return_qty} exceeds original qty {original_item.qty} for item {item_code}"
                    }
                
                # Add return item (negative quantity)
                return_invoice_data["items"].append({
                    "item_code": original_item.item_code,
                    "item_name": original_item.item_name,
                    "description": original_item.description,
                    "qty": -return_qty,  # Negative for return
                    "rate": original_item.rate,
                    "uom": original_item.uom,
                    "stock_uom": original_item.stock_uom,
                    "conversion_factor": original_item.conversion_factor,
                    "income_account": original_item.income_account,
                    "cost_center": original_item.cost_center,
                    "warehouse": original_item.warehouse if original_doc.update_stock else None
                })
        else:
            # Full return - return all items with full quantities
            for orig_item in original_doc.items:
                return_invoice_data["items"].append({
                    "item_code": orig_item.item_code,
                    "item_name": orig_item.item_name,
                    "description": orig_item.description,
                    "qty": -orig_item.qty,  # Negative for return
                    "rate": orig_item.rate,
                    "uom": orig_item.uom,
                    "stock_uom": orig_item.stock_uom,
                    "conversion_factor": orig_item.conversion_factor,
                    "income_account": orig_item.income_account,
                    "cost_center": orig_item.cost_center,
                    "warehouse": orig_item.warehouse if original_doc.update_stock else None
                })
        
        # Copy taxes from original invoice (will be auto-calculated as negative)
        for orig_tax in original_doc.taxes:
            return_invoice_data["taxes"].append({
                "charge_type": orig_tax.charge_type,
                "account_head": orig_tax.account_head,
                "description": orig_tax.description,
                "rate": orig_tax.rate,
                "cost_center": orig_tax.cost_center
            })
        
        # Create return invoice
        return_doc = frappe.get_doc(return_invoice_data)
        
        # Add return reason if provided
        if custom_return_reason:
            return_doc.custom_return_reason = custom_return_reason
        
        return_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Prepare response
        return {
            "status": "success",
            "message": f"Sales Return {return_doc.name} created successfully",
            "data": {
                "return_invoice": return_doc.name,
                "original_invoice": original_invoice,
                "customer": return_doc.customer,
                "company": return_doc.company,
                "posting_date": str(return_doc.posting_date),
                "is_return": return_doc.is_return,
                "return_against": return_doc.return_against,
                
                "net_total": return_doc.net_total,
                "tax_total": return_doc.total_taxes_and_charges,
                "grand_total": return_doc.grand_total,
                "outstanding_amount": return_doc.outstanding_amount,
                
                "items": [
                    {
                        "item_code": i.item_code,
                        "item_name": i.item_name,
                        "qty": i.qty,
                        "rate": i.rate,
                        "amount": i.amount,
                        "uom": i.uom
                    }
                    for i in return_doc.items
                ],
                
                "taxes": [
                    {
                        "description": t.description,
                        "rate": t.rate,
                        "tax_amount": t.tax_amount
                    }
                    for t in return_doc.taxes
                ]
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Sales Return API Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False, methods=["POST"])
def submit_sales_return():
    """
    Submit a Sales Return (Credit Note).
    
    Features:
    - Validates return invoice exists and is draft
    - Submits the return invoice
    - Updates stock if applicable
    - Updates outstanding amount of original invoice
    - Optionally creates refund payment entry
    
    Note: Payment entry creation is optional based on create_payment flag
    """
    
    try:
        data = json.loads(frappe.request.data) if frappe.request.data else frappe.form_dict
        
        return_invoice = data.get("return_invoice")
        if not return_invoice:
            return {"status": "error", "message": "return_invoice is required"}
        
        # Validate return invoice exists
        if not frappe.db.exists("Sales Invoice", return_invoice):
            return {"status": "error", "message": f"Sales Invoice '{return_invoice}' not found"}
        
        return_doc = frappe.get_doc("Sales Invoice", return_invoice)
        
        # Validate it's a return invoice
        if not return_doc.is_return:
            return {"status": "error", "message": "This is not a return invoice"}
        
        # Validate it's in draft state
        if return_doc.docstatus != 0:
            return {
                "status": "error",
                "message": f"Return invoice already submitted or cancelled. Status: {return_doc.docstatus}"
            }
        
        # Submit the return invoice
        return_doc.submit()
        frappe.db.commit()
        
        # Check if payment entry should be created
        create_payment = data.get("create_payment", False)
        payment_entry = None
        
        if create_payment:
            # Get payment mode (default to Cash if not specified)
            mode_of_payment = data.get("mode_of_payment", "Cash")
            
            # Validate mode of payment exists
            if not frappe.db.exists("Mode of Payment", mode_of_payment):
                return {
                    "status": "error",
                    "message": f"Mode of Payment '{mode_of_payment}' not found"
                }
            
            # Get company's receivable account
            receivable_account = frappe.db.get_value(
                "Company", return_doc.company, "default_receivable_account"
            )
            
            if not receivable_account:
                return {
                    "status": "error",
                    "message": "Default Receivable Account missing in Company settings"
                }
            
            # Get payment account from mode of payment
            payment_account = frappe.db.get_value(
                "Mode of Payment Account",
                {"parent": mode_of_payment, "company": return_doc.company},
                "default_account"
            )
            
            if not payment_account:
                return {
                    "status": "error",
                    "message": f"No account configured for Mode of Payment '{mode_of_payment}'"
                }
            
            # Create Payment Entry for refund
            pe = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Pay",  # Pay because we're refunding to customer
                "posting_date": return_doc.posting_date,
                "company": return_doc.company,
                "party_type": "Customer",
                "party": return_doc.customer,
                
                "paid_from": payment_account,  # Pay from cash/bank
                "paid_to": receivable_account,  # Pay to receivable (reduces customer balance)
                
                "mode_of_payment": mode_of_payment,
                
                "paid_amount": abs(return_doc.grand_total),  # Absolute value
                "received_amount": abs(return_doc.grand_total),
                
                "references": [
                    {
                        "reference_doctype": "Sales Invoice",
                        "reference_name": return_doc.name,
                        "total_amount": return_doc.grand_total,
                        "outstanding_amount": return_doc.outstanding_amount,
                        "exchange_rate": 1,
                        "allocated_amount": abs(return_doc.grand_total)
                    }
                ]
            })
            
            pe.insert(ignore_permissions=True)
            pe.submit()
            frappe.db.commit()
            
            payment_entry = pe.name
        
        # Prepare response
        return {
            "status": "success",
            "message": "Sales Return submitted successfully" + (
                " with refund payment" if payment_entry else ""
            ),
            "data": {
                "return_invoice": return_doc.name,
                "original_invoice": return_doc.return_against,
                "docstatus": return_doc.docstatus,
                "payment_entry": payment_entry,
                "grand_total": return_doc.grand_total,
                "outstanding_amount": return_doc.outstanding_amount
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Submit Sales Return Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_return_details():
    """
    Get details of a Sales Return invoice.
    
    Returns:
    - Return invoice details
    - Original invoice reference
    - Items returned
    - Tax details
    - Payment entry (if exists)
    """
    
    try:
        return_invoice = frappe.form_dict.get("return_invoice")
        
        if not return_invoice:
            return {"status": "error", "message": "return_invoice parameter is required"}
        
        if not frappe.db.exists("Sales Invoice", return_invoice):
            return {"status": "error", "message": f"Sales Invoice '{return_invoice}' not found"}
        
        return_doc = frappe.get_doc("Sales Invoice", return_invoice)
        
        if not return_doc.is_return:
            return {"status": "error", "message": "This is not a return invoice"}
        
        # Get payment entry if exists
        payment_entries = frappe.get_all(
            "Payment Entry Reference",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": return_invoice,
                "docstatus": 1
            },
            fields=["parent as payment_entry"]
        )
        
        return {
            "status": "success",
            "data": {
                "return_invoice": return_doc.name,
                "original_invoice": return_doc.return_against,
                "customer": return_doc.customer,
                "customer_name": return_doc.customer_name,
                "company": return_doc.company,
                
                "posting_date": str(return_doc.posting_date),
                "due_date": str(return_doc.due_date),
                
                "docstatus": return_doc.docstatus,
                "status": "Draft" if return_doc.docstatus == 0 else "Submitted" if return_doc.docstatus == 1 else "Cancelled",
                
                "is_return": return_doc.is_return,
                "return_against": return_doc.return_against,
                
                "net_total": return_doc.net_total,
                "tax_total": return_doc.total_taxes_and_charges,
                "grand_total": return_doc.grand_total,
                "rounded_total": return_doc.rounded_total or return_doc.grand_total,
                "outstanding_amount": return_doc.outstanding_amount,
                
                "update_stock": return_doc.update_stock,
                
                "items": [
                    {
                        "item_code": i.item_code,
                        "item_name": i.item_name,
                        "description": i.description,
                        "qty": i.qty,
                        "rate": i.rate,
                        "amount": i.amount,
                        "uom": i.uom,
                        "warehouse": i.warehouse
                    }
                    for i in return_doc.items
                ],
                
                "taxes": [
                    {
                        "description": t.description,
                        "charge_type": t.charge_type,
                        "account_head": t.account_head,
                        "rate": t.rate,
                        "tax_amount": t.tax_amount
                    }
                    for t in return_doc.taxes
                ],
                
                "payment_entries": [pe["payment_entry"] for pe in payment_entries] if payment_entries else []
            }
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Return Details Error")
        return {"status": "error", "message": str(e)}




@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_returns_list():
    """
    Get list of all Sales Returns.

    Filters:
    - customer
    - from_date
    - to_date
    - status (0=Draft, 1=Submitted, 2=Cancelled)
    - original_invoice

    Returns:
    - Full list (no pagination)
    - Latest first
    """

    try:
        filters = {"is_return": 1}

        # Customer filter
        if frappe.form_dict.get("customer"):
            filters["customer"] = frappe.form_dict.get("customer")

        # Date range filter
        from_date = frappe.form_dict.get("from_date")
        to_date = frappe.form_dict.get("to_date")

        if from_date and to_date:
            filters["posting_date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["posting_date"] = [">=", from_date]
        elif to_date:
            filters["posting_date"] = ["<=", to_date]

        # Status filter
        if frappe.form_dict.get("status"):
            filters["docstatus"] = cint(frappe.form_dict.get("status"))

        # Original invoice filter
        if frappe.form_dict.get("original_invoice"):
            filters["return_against"] = frappe.form_dict.get("original_invoice")

        # Fetch all (NO LIMIT)
        returns = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=[
                "name",
                "customer",
                "customer_name",
                "posting_date",
                "return_against",
                "grand_total",
                "outstanding_amount",
                "docstatus"
            ],
            order_by="posting_date desc, modified desc"
        )

        # Add readable status
        for ret in returns:
            ret["status"] = (
                "Draft" if ret.docstatus == 0 else
                "Submitted" if ret.docstatus == 1 else
                "Cancelled"
            )

        return {
            "status": "success",
            "total": len(returns),
            "data": returns
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Returns List Error")
        return {"status": "error", "message": str(e)}






@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_stock_balance_summary():

    try:
        warehouse = frappe.form_dict.get("warehouse")
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")

        conditions = []

        if warehouse:
            conditions.append(f"sle.warehouse = '{warehouse}'")

        if company:
            conditions.append(f"wh.company = '{company}'")

        where_clause = " AND " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT 
                COUNT(DISTINCT sle.item_code) as total_items,
                SUM(sle.qty_after_transaction) as total_quantity,
                SUM(sle.stock_value) as stock_value
            FROM 
                (
                    SELECT 
                        item_code,
                        warehouse,
                        qty_after_transaction,
                        stock_value,
                        ROW_NUMBER() OVER (PARTITION BY item_code, warehouse 
                                           ORDER BY posting_date DESC, posting_time DESC, creation DESC) as rn
                    FROM `tabStock Ledger Entry`
                    WHERE docstatus < 2
                ) sle
            INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
            WHERE sle.rn = 1
            AND sle.qty_after_transaction > 0
            {where_clause}
        """

        result = frappe.db.sql(query, as_dict=True)

        currency = frappe.db.get_value("Company", company, "default_currency") if company else "SAR"

        summary = result[0] if result else {}

        return {
            "status": "success",
            "data": {
                "total_items": cint(summary.get("total_items", 0)),
                "total_quantity": flt(summary.get("total_quantity", 0), 2),
                "stock_value": flt(summary.get("stock_value", 0), 2),
                "currency": currency or "SAR"
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Stock Summary Error")
        return {"status": "error", "message": str(e)}



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_stock_levels():

    try:
        warehouse = frappe.form_dict.get("warehouse")
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")
        item_code_search = frappe.form_dict.get("item_code")
        item_name_search = frappe.form_dict.get("item_name")
        general_search = frappe.form_dict.get("search")

        conditions = ["sle.qty_after_transaction > 0"]

        if warehouse:
            conditions.append(f"sle.warehouse = '{warehouse}'")
        if company:
            conditions.append(f"wh.company = '{company}'")
        if item_code_search:
            conditions.append(f"item.item_code LIKE '%{item_code_search}%'")
        if item_name_search:
            conditions.append(f"item.item_name LIKE '%{item_name_search}%'")
        if general_search:
            conditions.append(f"(item.item_code LIKE '%{general_search}%' OR item.item_name LIKE '%{general_search}%')")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT 
                item.item_code,
                item.item_name,
                item.stock_uom as uom,
                sle.warehouse,
                sle.qty_after_transaction as stock_qty,
                item.valuation_rate as cost_price,
                item.standard_rate as sale_price,
                sle.stock_value,
                CASE WHEN sle.qty_after_transaction > 0 THEN 'In Stock' ELSE 'Out of Stock' END status
            FROM 
                (
                    SELECT 
                        item_code,
                        warehouse,
                        qty_after_transaction,
                        stock_value,
                        ROW_NUMBER() OVER (PARTITION BY item_code, warehouse 
                                           ORDER BY posting_date DESC, posting_time DESC, creation DESC) rn
                    FROM `tabStock Ledger Entry`
                    WHERE docstatus < 2
                ) sle
            INNER JOIN `tabItem` item ON item.name = sle.item_code
            INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
            WHERE sle.rn = 1 AND {where_clause}
            ORDER BY item.item_code ASC
        """

        items = frappe.db.sql(query, as_dict=True)

        return {
            "status": "success",
            "data": {
                "items": [{
                    "item_code": i.item_code,
                    "item_name": i.item_name,
                    "uom": i.uom,
                    "warehouse": i.warehouse,
                    "stock_qty": flt(i.stock_qty, 2),
                    "cost_price": flt(i.cost_price, 2),
                    "sale_price": flt(i.sale_price, 2),
                    "stock_value": flt(i.stock_value, 2),
                    "status": i.status
                } for i in items]
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Stock Level Error")
        return {"status": "error", "message": str(e)}



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_warehouses():
    """
    Get list of all warehouses for the warehouse filter dropdown.
    
    Query Parameters:
    - company: Filter by company (optional)
    
    Returns:
    {
        "status": "success",
        "data": [
            {
                "warehouse": "MAIN",
                "warehouse_name": "Main Warehouse"
            }
        ]
    }
    """
    
    try:
        company = frappe.form_dict.get("company") or frappe.defaults.get_user_default("Company")
        
        conditions = []
        if company:
            conditions.append(f"company = '{company}'")
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT 
                name as warehouse,
                warehouse_name
            FROM `tabWarehouse`
            {where_clause}
            ORDER BY warehouse_name ASC
        """
        
        warehouses = frappe.db.sql(query, as_dict=True)
        
        return {
            "status": "success",
            "data": warehouses
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Warehouses Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_stock_balance_complete():
    """
    Get complete stock balance data - combines summary and detailed items in one call.
    This is useful for loading the entire page with a single API request.
    
    Query Parameters:
    - warehouse: Filter by warehouse (optional)
    - company: Filter by company (optional)
    - search: Search items (optional)
    - limit: Number of items (default: 100)
    - offset: Pagination offset (default: 0)
    
    Returns:
    {
        "status": "success",
        "data": {
            "summary": {
                "total_items": 7,
                "total_quantity": 1420,
                "stock_value": 12110.00,
                "currency": "SAR"
            },
            "items": [...],
            "warehouses": [...],
            "pagination": {...}
        }
    }
    """
    
    try:
        # Get summary
        summary_response = get_stock_balance_summary()
        if summary_response["status"] != "success":
            return summary_response
        
        # Get items
        items_response = get_stock_levels()
        if items_response["status"] != "success":
            return items_response
        
        # Get warehouses
        warehouses_response = get_warehouses()
        if warehouses_response["status"] != "success":
            return warehouses_response
        
        return {
            "status": "success",
            "data": {
                "summary": summary_response["data"],
                "items": items_response["data"]["items"],
                "warehouses": warehouses_response["data"],
                "pagination": items_response["data"]["pagination"]
            }
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Stock Balance Complete Error")
        return {
            "status": "error",
            "message": str(e)
        }