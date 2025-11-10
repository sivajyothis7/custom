import frappe
from frappe import _
from frappe.utils import formatdate
from hrms.hr.doctype.leave_allocation.leave_allocation import LeaveAllocation
from frappe.utils import add_months, nowdate, get_first_day, get_last_day, getdate

def allocate_comp_off():
    """Allocate 1 Compensatory Off for employees who worked >10 extra hours in the previous month."""
    today = getdate(nowdate())
    prev_month_start = get_first_day(add_months(today, -1))
    prev_month_end = get_last_day(add_months(today, -1))

    employees = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "default_shift"])

    for emp in employees:
        if not emp.default_shift:
            continue

        shift = frappe.get_doc("Shift Type", emp.default_shift)
        shift_duration_hours = (
            (shift.end_time - shift.start_time).total_seconds() / 3600
        )

        attendances = frappe.db.sql(
            """
            SELECT SUM(working_hours)
            FROM `tabAttendance`
            WHERE employee = %s
              AND attendance_date BETWEEN %s AND %s
              AND docstatus = 1
            """,
            (emp.name, prev_month_start, prev_month_end),
        )[0][0] or 0

        days_worked = frappe.db.count("Attendance", {
            "employee": emp.name,
            "attendance_date": ["between", [prev_month_start, prev_month_end]],
            "docstatus": 1,
        })
        total_shift_hours = days_worked * shift_duration_hours

        extra_hours = attendances - total_shift_hours

        if extra_hours >= 10:
            existing = frappe.db.exists(
                "Leave Allocation",
                {
                    "employee": emp.name,
                    "leave_type": "Compensatory Off",
                    "from_date": get_first_day(today),
                    "docstatus": ["!=", 2],
                },
            )
            if existing:
                continue

            allocation = frappe.new_doc("Leave Allocation")
            allocation.employee = emp.name
            allocation.leave_type = "Compensatory Off"
            allocation.from_date = get_first_day(today)
            allocation.to_date = add_months(today, 3)
            allocation.new_leaves_allocated = 1
            allocation.description = (
                f"Auto Comp Off for {int(extra_hours)} extra hours worked in {prev_month_start.strftime('%B %Y')}"
            )
            
            allocation.insert(ignore_permissions=True)
            
            frappe.logger().info(f"Created draft Comp Off allocation for {emp.name} ({int(extra_hours)} extra hours)")





class CustomLeaveAllocation(LeaveAllocation):
    """Custom Leave Allocation that only warns on overlap instead of throwing."""

    def validate_allocation_overlap(self):
        leave_allocation = frappe.db.sql(
            """
            SELECT
                name
            FROM `tabLeave Allocation`
            WHERE
                employee=%s AND leave_type=%s
                AND name <> %s AND docstatus=1
                AND to_date >= %s AND from_date <= %s
            """,
            (self.employee, self.leave_type, self.name, self.from_date, self.to_date),
        )

        if leave_allocation:
            frappe.msgprint(
                _(
                    "{0} already allocated for Employee {1} for period {2} to {3}. "
                    "Existing allocation: <a href='/app/leave-allocation/{4}'>{4}</a>"
                ).format(
                    self.leave_type,
                    self.employee,
                    formatdate(self.from_date),
                    formatdate(self.to_date),
                    leave_allocation[0][0],
                ),
                alert=True,
                indicator="orange",
            )

            frappe.log_error(
                title="Leave Allocation Overlap (Warning Only)",
                message=f"Overlap detected for {self.employee} - {self.leave_type} "
                        f"with existing allocation {leave_allocation[0][0]}"
            )

            return





def create_user_in_external_system(doc, method):
    
    api_url = "https://office.enfono.com/api/resource/User"
    
    api_token = "1f99f5f4dc07b6a:258901802466295"
    
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": doc.name,          
        "first_name": doc.first_name,     
        "email": doc.email,          
    }
    
    frappe.logger().info(f"Sending payload to external system: {payload}")

    try:
        response = requests.get(f"{api_url}/{doc.email}", headers=headers)
        
        if response.status_code == 200:
            response = requests.put(f"{api_url}/{doc.email}", json=payload, headers=headers)
            if response.status_code in [200, 201]:
                frappe.msgprint(f"User {doc.username} updated successfully in external system.")
            else:
                frappe.throw(f"Failed to update user in external system: {response.text}")
        elif response.status_code == 404:
            response = requests.post(api_url, json=payload, headers=headers)
            if response.status_code in [200, 201]:
                frappe.msgprint(f"User {doc.username} created successfully in external system.")
            else:
                frappe.throw(f"Failed to create user in external system: {response.text}")
        else:
            frappe.throw(f"Failed to check user existence in external system: {response.text}")
        
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Error creating or updating user in external system: {str(e)}")



@frappe.whitelist(allow_guest=True)
def send_created_item_details(doc, method=None):
    try:
        frappe.logger().debug(f"Received doc: {doc.as_dict()}")

        item_details = {
            "code": doc.item_code,
            "name": doc.item_name,
            "rate": 0,
            "uom": doc.stock_uom,
            "sourceId": doc.name
        }

        frappe.logger().debug(f"Sending item details: {item_details}")

        mobile_app_url = "https://uat.industree.org.in/api/v1/production-item/create"

        response = requests.post(
            mobile_app_url,
            json=item_details,
            headers={"Content-Type": "application/json"}
        )

        frappe.logger().debug(f"Response Status Code: {response.status_code}")
        frappe.logger().debug(f"Response Content: {response.text}")

        if response.status_code == 200:
            frappe.logger().info(f"Item sent successfully to mobile app: {item_details}")
            frappe.msgprint(f"Item {doc.item_code} created successfully in the external system.")
        else:
            frappe.log_error(
                message=f"Failed to send item to mobile app. Response: {response.text}",
                title="Item Sync Error"
            )
            frappe.msgprint(f"Failed to send item {doc.item_code} to external system. Please try again.")

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            message=f"Network error while sending item to external system: {str(e)}",
            title="Item Sync Network Error"
        )
        frappe.msgprint(f"Network error: {str(e)}")

    except Exception as e:
        frappe.log_error(
            message=f"Unexpected error while sending item details: {str(e)}",
            title="Error in send_created_item_details"
        )
        frappe.msgprint(f"An unexpected error occurred: {str(e)}")
