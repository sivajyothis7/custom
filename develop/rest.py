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





@frappe.whitelist(allow_guest=True)
def custom_login(username, password):
    """
    Custom login function supporting both email and mobile number as the username.
    """
    try:
        frappe.logger().info(f"Attempting login for username: {username}")

        if "@" in username and "." in username:
            user = frappe.db.get_value("User", {"email": username}, ["name", "enabled", "email", "mobile_no"], as_dict=True)
        else:
            user = frappe.db.get_value("User", {"mobile_no": username}, ["name", "enabled", "email", "mobile_no"], as_dict=True)

        if not user:
            frappe.logger().error(f"User with username {username} does not exist.")
            frappe.local.response["http_status_code"] = 400
            frappe.local.response["message"] = {
                "success_key": 0,
                "message": _("Invalid email/ mobile number or password.")
            }
            return

        if not user["enabled"]:
            frappe.logger().error(f"User with username {username} is disabled.")
            frappe.local.response["http_status_code"] = 400
            frappe.local.response["message"] = {
                "success_key": 0,
                "message": _("User is disabled. Please contact the administrator.")
            }
            return

        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=user["email"], pwd=password)
        frappe.logger().info(f"User with username {username} authenticated successfully.")

        login_manager.post_login()
        frappe.logger().info(f"Post-login setup completed for user {user['email']}.")

        user_doc = frappe.get_doc('User', frappe.session.user)

        frappe.local.response["http_status_code"] = 200
        frappe.local.response["message"] = {
            "message": _("Login successful."),
            "username": user_doc.username or user_doc.first_name,
            "email": user_doc.email,
            "mobile_number": user_doc.mobile_no
        }
    except frappe.exceptions.AuthenticationError:
        frappe.logger().error(f"Authentication failed for username: {username}")
        frappe.clear_messages()
        frappe.local.response["http_status_code"] = 400
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": _("Invalid email/ mobile number or password.")
        }

@frappe.whitelist(allow_guest=True)
def get_units():
    # Fetch all EOI records
    eoi_records = frappe.get_all(
        "EOI For Land",
        fields=["name"]
    )
    
    # Prepare a list to store unit data
    unit_data = []

    for record in eoi_records:
        # Fetch units with type "Unit"
        units = frappe.get_all(
            "Units and Sub units",
            filters={"parent": record["name"], "type": "Unit"},
            fields=["name1"]
        )
        
        # Add each unit as a separate dictionary to the response
        for unit in units:
            unit_data.append({"unit": unit["name1"]})
    
    return unit_data



@frappe.whitelist(allow_guest=True)
def get_sub_units():
    eoi_records = frappe.get_all(
        "EOI For Land",
        fields=["name", "district"]
    )
    
    for record in eoi_records:
        sub_units = frappe.get_all(
            "Units and Sub units",
            filters={"parent": record["name"], "type": "Sub Unit"},
            fields=["name1"]
        )
        
        record["sub_unit"] = [sub_unit["name1"] for sub_unit in sub_units]
    
    return eoi_records

# @frappe.whitelist(allow_guest=True)
# def get_eoi_with_units():
#     eoi_records = frappe.get_all(
#         "EOI For Land",
#         fields=["name", "district"]
#     )
    
#     for record in eoi_records:
#         units = frappe.get_all(
#             "Units and Sub units",
#             filters={"parent": record["name"]},
#             fields=["name1"]
#         )
        
#         record["name1_values"] = [unit["name1"] for unit in units]
    
#     return eoi_records
