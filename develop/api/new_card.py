import frappe
from frappe.utils import today

@frappe.whitelist()
def get_total_mada_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Mada'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_master_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Master'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_card_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Card'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_cash_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Cash'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_american_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'American Express'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_visa_payments():
    posting_date = today()
    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Visa'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_bank_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND sip.mode_of_payment = 'Bank Transfer'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

########################## Store Wise ########################
@frappe.whitelist()

def get_total_fleurs_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT SUM(sip.amount) AS total_amount
        FROM tabSales Invoice Payment sip 
        JOIN tabPOS Invoice pi ON sip.parent = pi.name
        WHERE 
        sip.parenttype = 'POS Invoice'
        AND pi.pos_profile = 'FLEURS DE VIE'
        AND pi.posting_date = %s
        AND pi.docstatus = 1
        """, (posting_date,), as_dict = True)
    total = rows[0]['total_amount'] if rows else 0

    return {
        "value" : total,
        "fieldtype" : "Currency"
    }
               

@frappe.whitelist()
def get_total_camilia_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND pi.pos_profile = 'Camilia Store'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_concept_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND pi.pos_profile = 'Concept Store'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_chelsie_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND pi.pos_profile = 'Chelsie Lane'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

@frappe.whitelist()
def get_total_boulevard_payments():
    posting_date = today()

    rows = frappe.db.sql("""
        SELECT
            SUM(sip.amount) AS total_amount
        FROM
            tabSales Invoice Payment sip
        JOIN
            tabPOS Invoice pi ON sip.parent = pi.name
        WHERE
            sip.parenttype = 'POS Invoice'
            AND pi.pos_profile = 'Boulevard Runway'
            AND pi.posting_date = %s
            AND pi.docstatus = 1
    """, (posting_date,), as_dict=True)

    total = rows[0]['total_amount'] if rows else 0

    return {
        "value": total,
        "fieldtype": "Currency"
    }

