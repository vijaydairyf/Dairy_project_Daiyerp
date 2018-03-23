# Copyright (c) 2013, indictrans technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns, data = [], []
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):

	columns =[ ("Farmer ID") + ":Link/Farmer:200",
				("Farmer") + ":Data:200",
				("Date") + ":Datetime:150",
				("Shift") + ":Data:150",
				("Milk Type") + ":Data:150",
				("Quantity") + ":Int:150",
				("Amount") + ":Currency:150"			
			]
	return columns

def get_conditions(filters):
	conditions = " and 1=1"
	if filters.get('farmer_id'):
		conditions += " and farmerid = '{0}'".format(filters.get('farmer_id'))
	if filters.get('shift'):
		conditions += " and shift = '{0}'".format(filters.get('shift'))
	if filters.get('from_date') and filters.get('to_date'):
		conditions += " and date(rcvdtime) between '{0}' and '{1}' ".format(filters.get('from_date'),filters.get('to_date'))
	return conditions

def get_data(filters):
	user_doc = frappe.db.get_value("User",{"name":frappe.session.user},['operator_type','company','branch_office'], as_dict =1)
	data = frappe.db.sql("""select farmerid,farmer,rcvdtime,shift,milktype,milkquantity,amount
				from `tabFarmer Milk Collection Record` where
				associated_vlcc = '{0}' {1}""".format(
					user_doc.get('company'),
					get_conditions(filters)),as_list=True)

	return data

