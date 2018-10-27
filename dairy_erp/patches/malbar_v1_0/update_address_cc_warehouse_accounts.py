# critical patch for updating warehouse and accounts on address
from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("""
		update 
			`tabAddress` 
		set 
			warehouse = 'Pattambi - MM', rejected_warehouse = 'Pattambi-Rejected - MM', income_account = 'Pattambi Income - MM', expence_account = 'Pattambi Expense - MM', stock_account = 'Pattambi Stock - MM'
		where 
			name = 'Pattambi-Chilling Centre' """)
