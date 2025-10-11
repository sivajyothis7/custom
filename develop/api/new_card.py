import frappe
from frappe.utils import today

# -------------------------- PAYMENT MODE WISE --------------------------

@frappe.whitelist()
def get_total_mada_payments():
    return get_total_by_mode_of_payment("Mada")

@frappe.whitelist()
def get_total_master_payments():
    return get_total_by_mode_of_payment("Master")

@frappe.whitelist()
def get_total_card_payments():
    return get_total_by_mode_of_payment("Card")

@frappe.whitelist()
def get_total_cash_payments():
    return get_total_by_mode_of_payment("Cash")

@frappe.whitelist()
def get_total_american_payments():
    return get_total_by_mode_of_payment("American Express")

@frappe.whitelist()
def get_total_visa_payments():
    return get_total_by_mode_of_payment("Visa")

@frappe.whitelist()
def get_total_bank_payments():
    return get_total_by_mode_of_payment("Bank Transfer")

# -------------------------- STORE WISE --------------------------

@frappe.whitelist()
def get_total_fleurs_payments():
    return get_total_by_pos_profile("FLEURS DE VIE")

@frappe.whitelist()
def get_total_camilia_payments():
    return get_total_by_pos_profile("Camilia Store")

@frappe.whitelist()
def get_total_concept_payments():
    return get_total_by_pos_profile("Concept Store")

@frappe.whitelist()
def get_total_chelsie_payments():
    return get_total_by_pos_profile("Chelsie Lane")

@frappe.whitelist()
def get_total_boulevard_payments():
    return get_total_by_pos_profile("Boulevard Runway")

# -------------------------- HELPER FUNCTIONS --------------------------

def get_total_by_mode_of_payment(mode_of_payment):
    """Return total payments by Mode of Payment for today's POS Invoices"""
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            `tabSales Invoice Payment` AS sip
        JOIN
            `tabPOS Invoice` AS pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = %s
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (mode_of_payment, posting_date), as_dict=True)

    total = rows[0]['total_amount'] if rows and rows[0]['total_amount'] else 0
    return {"value": total, "fieldtype": "Currency"}


def get_total_by_pos_profile(pos_profile):
    """Return total payments by POS Profile (Store) for today's POS Invoices"""
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            `tabSales Invoice Payment` AS sip
        JOIN
            `tabPOS Invoice` AS pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND pi.pos_profile = %s
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (pos_profile, posting_date), as_dict=True)

    total = rows[0]['total_amount'] if rows and rows[0]['total_amount'] else 0
    return {"value": total, "fieldtype": "Currency"}
