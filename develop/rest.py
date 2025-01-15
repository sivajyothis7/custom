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
def custom_login(mobile_number, password):
    try:
        frappe.logger().info(f"Attempting login for mobile number: {mobile_number}")

        user = frappe.db.get_value("User", {"mobile_no": mobile_number}, ["name", "enabled", "email"], as_dict=True)
        if not user:
            frappe.logger().error(f"User with mobile number {mobile_number} does not exist.")
            frappe.local.response["http_status_code"] = 401
            frappe.throw(_("Invalid mobile number or password."), frappe.exceptions.AuthenticationError)

        if not user["enabled"]:
            frappe.logger().error(f"User with mobile number {mobile_number} is disabled.")
            frappe.local.response["http_status_code"] = 403
            frappe.throw(_("User is disabled. Please contact the administrator."), frappe.exceptions.AuthenticationError)

        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=user["email"], pwd=password)
        frappe.logger().info(f"User with mobile number {mobile_number} authenticated successfully.")

        login_manager.post_login()
        frappe.logger().info(f"Post-login setup completed for user {user['email']}.")

        user_doc = frappe.get_doc('User', frappe.session.user)
        api_secret = generate_keys(user_doc)

        frappe.local.response["message"] = {
            "success_key": 1,
            "message": _("Authentication successful."),
            "sid": frappe.session.sid,
            "username": user_doc.username or user_doc.first_name,
            "email": user_doc.email,
            "mobile_number": user_doc.mobile_no,
            "api_key": user_doc.api_key,
            "api_secret": api_secret
        }
    except frappe.exceptions.AuthenticationError as e:
        frappe.logger().error(f"Authentication failed for mobile number: {mobile_number}: {str(e)}")
        frappe.local.response["http_status_code"] = 401
        frappe.throw(_("Invalid mobile number or password."), frappe.exceptions.AuthenticationError)


def generate_keys(user):
    """
    Generate API Key and API Secret for the user if they don't already exist.
    """
    api_secret = frappe.generate_hash(length=15)
    if not user.api_key:
        user.api_key = frappe.generate_hash(length=15)

    user.api_secret = api_secret
    user.save(ignore_permissions=True)

    frappe.logger().info(f"Generated API Key: {user.api_key}, API Secret: {api_secret}")
    return api_secret


@frappe.whitelist(allow_guest=True)
def get_units():
    eoi_records = frappe.get_all(
        "EOI For Land",
        fields=["name"]
    )
    
    unit_data = []

    for record in eoi_records:
        units = frappe.get_all(
            "Units and Sub units",
            filters={"parent": record["name"], "type": "Unit"},
            fields=["name1"]
        )
        
        for unit in units:
            unit_data.append({"unit": unit["name1"]})
    
    return unit_data



@frappe.whitelist(allow_guest=True)
def get_sub_units():
    eoi_records = frappe.get_all(
        "EOI For Land",
        fields=["name"]
    )
    
    sub_unit_data = []

    for record in eoi_records:
        sub_units = frappe.get_all(
            "Units and Sub units",
            filters={"parent": record["name"], "type": "Sub Unit"},
            fields=["name1"]
        )
        
        for sub_unit in sub_units:
            sub_unit_data.append({"sub_unit": sub_unit["name1"]})
    
    return sub_unit_data




@frappe.whitelist(allow_guest=False)
def user_cred():
    user = frappe.session.user 
    
    user_doc = frappe.get_doc("User", user)
    
    if frappe.request.method == "GET":
        return {
            "full_name": user_doc.full_name,
            "mobile_no": user_doc.mobile_no,
            "email": user_doc.email,
            "location": user_doc.location 
        }
    
    elif frappe.request.method == "PUT":
        first_name = frappe.local.form_dict.get('first_name')
        last_name = frappe.local.form_dict.get('last_name')
        mobile_no = frappe.local.form_dict.get('mobile_no')
        location = frappe.local.form_dict.get('location')
        
        if first_name:
            user_doc.first_name = first_name

        if last_name:
            user_doc.last_name = last_name

        if mobile_no:
            user_doc.mobile_no = mobile_no

    

        if location is not None: 
            user_doc.location = location
        
        user_doc.save()
        frappe.db.commit()

        return {"message": _("User details updated successfully")}




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
