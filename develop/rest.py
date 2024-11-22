import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def custom_signup(mobile_number, password, full_name, email, password_confirmation):
    

    existing_user = frappe.db.exists("User", {"mobile_no": mobile_number, "email": email})
    if existing_user:
        return {"status": "error", "message": _("User already registered with this mobile number/ email.")}

    if not (mobile_number and password and full_name and email and password_confirmation):
        return {"status": "error", "message": _("All fields are required.")}

    if len(password) != 4 or not password.isdigit():
        return {"status": "error", "message": _("Password must be exactly 4 digits.")}

    if password != password_confirmation:
        return {"status": "error", "message": _("Password and confirmation do not match.")}

    existing_user_by_email = frappe.db.exists("User", {"email": email})
    if existing_user_by_email:
        return {"status": "error", "message": _("Email already exists. Please try a new one.")}

    if len(mobile_number) != 10 or not mobile_number.isdigit():
        return {"status": "error", "message": _("Mobile number must be exactly 10 digits.")}

    existing_user_by_mobile = frappe.db.exists("User", {"mobile_no": mobile_number})
    if existing_user_by_mobile:
        return {"status": "error", "message": _("Mobile number already exists. Please try a new one.")}

    existing_user_by_name = frappe.db.exists("User", {"first_name": full_name})
    if existing_user_by_name:
        return {"status": "error", "message": _("This name already exists. Please try a new one.")}

    

    try:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "mobile_no": mobile_number,
            "enabled": 1,
            "new_password": password,  
            "user_type": "Website User",
            "send_welcome_email": False  
        })
        user.insert(ignore_permissions=True)

        return {"status": "success", "message": _("User created successfully.")}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Custom Signup Error")
        return {"status": "error", "message": _("An error occurred. Please try again.")}

