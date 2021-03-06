# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import json


@frappe.whitelist()
def make_po(data,doc):
	data = json.loads(data)
	doc = json.loads(doc)
	po_doc = frappe.new_doc("Purchase Order")
	po_doc.supplier = data.get('supplier')
	for row in doc.get('items'):
		po_doc.append("items", {
			"item_code": row.get('item_code'),
			"item_name": row.get('item_name'),
			"description": row.get('description'),
			"qty": row.get('qty'),
			"uom": row.get('uom'),
			"schedule_date": row.get('schedule_date'),
			"warehouse":data.get('warehouse')
		})
	po_doc.flags.ignore_permissions = True
	po_doc.flags.ignore_mandatory = True
	po_doc.save()
	po_doc.submit()

@frappe.whitelist()
def validate(doc,method):
	for item in doc.items:
		if item.qty < 0.00:
			frappe.throw(_("Quantity should not be negative"))

	# set cc flag if cc user
	operator_type = frappe.db.get_value("User", frappe.session.user, "operator_type")
	if operator_type == "Chilling Centre":
		doc.chilling_centre = 1


@frappe.whitelist()
def update_status(status,name):
	mi = frappe.get_doc("Material Request", name)
	frappe.db.sql("""update `tabMaterial Request` set status = '{0}' where name ='{1}' """.format(status,name))