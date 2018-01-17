
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt, cstr, cint
import time
from frappe import _
import dairy_utils as utils
import requests
from item_api import get_seesion_company_datails
import json

@frappe.whitelist()
def create_pr(data):
	response_dict, response_data = {}, []
	try:
		data_ = json.loads(data)
		if data_:
			if data_.get('client_id') and data_.get('supplier'):
				if cint(data_.get('additional_discount_percentage')) < 100:
					pr_exist = frappe.db.get_value("Purchase Receipt",{"client_id":data_.get('client_id')}, 'name')
					if not pr_exist:
						response_dict.update({"status": "success","name": make_pr(data_)})
					else:
						response_dict.update({"status": "success", "name": pr_exist})
				else:
					frappe.throw('Percentage not grater than 100')
			else:
				response_dict.update({"status":"error", "response":"client id, camp office , item are required "})
	except Exception,e:
		response_dict.update({"status":"error","message":e,"traceback":frappe.get_traceback()})
	return response_dict

def make_pr(data):
	pr_obj = frappe.new_doc("Purchase Receipt")
	pr_obj.update(data)
	pr_obj.flags.ignore_permissions = True
	pr_obj.insert()
	pr_obj.submit()

	return pr_obj.name


@frappe.whitelist()
def get_po_attr(supplier):
	"""Make PR for With PO reference attributes"""	
	try:
		response_dict, response_data = {}, []
		if frappe.db.exists('Supplier',supplier):
			po_list = frappe.db.sql("""select name from `tabPurchase Order` where supplier = '{0}' and status in ('To Receive and Bill')""".format(supplier),as_dict=1)
			for row in po_list:
				row.update({"items": frappe.db.sql("select item_code,rate,qty from `tabPurchase Order Item` where parent = '{0}'".format(row.get('name')),as_dict=1)})
			response_dict.update({"status":"success", "data": po_list})
		else:
			frappe.throw("Supplier does not exist")
	except Exception,e:
		response_dict.update({"status":"error","message":e,"traceback":frappe.get_traceback()})

	return response_dict

@frappe.whitelist()
def get_mi_attr():
	response_dict = {}
	try:
		mr_list = frappe.db.sql("select name from `tabMaterial Request` where company = '{0}' and status = 'Ordered'".format(get_seesion_company_datails().get('company')),as_dict=1)
		for row in mr_list:
			row.update({"items": frappe.db.sql("select item_code,qty from `tabMaterial Request Item` where parent = '{0}'".format(row.get('name')),as_dict=1)})
		response_dict.update({"status":"success","data": mr_list})
	except Exception,e:
		response_dict.update({"status":"error","message":e,"traceback":frappe.get_traceback()})
	return response_dict


@frappe.whitelist()
def get_pr_list():
	response_dict = {}
	try:
		pr_list = frappe.db.sql("""select company,name,posting_date,additional_discount_percentage,supplier,taxes_and_charges from `tabPurchase Receipt` where company = '{0}' and status in ('To Bill') order by creation desc limit 10 """.format(get_seesion_company_datails().get('company')),as_dict=1)
		for row in pr_list:
			row.update({"items": frappe.db.sql("select item_code,qty,rate from `tabPurchase Receipt Item` where parent = '{0}'".format(row.get('name')),as_dict=1)})
			if row.get('taxes_and_charges'):
				row.update({row.get('taxes_and_charges'): frappe.db.sql("""select charge_type,description,rate from `tabPurchase Taxes and Charges` where parent = '{0}'""".format(row.get('name')),as_dict=1)})
		response_dict.update({"status":"success","data":pr_list})
	except Exception,e:
		response_dict.update({"status":"error","message":e,"traceback":frappe.get_traceback()})
	return response_dict