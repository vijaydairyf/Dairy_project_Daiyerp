# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt
# Author Stellapps Technologies Private Ltd.

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate,flt, cstr, cint, has_common
import time
from frappe import _
import api_utils as utils
import requests
import json
from dairy_erp.report.farmer_net_payoff.farmer_net_payoff import get_data
from erpnext.stock.stock_balance import get_balance_qty_from_sle
from customization.price_list.price_list_customization import validate_price_list
from customization.stock_balance.stock_balance_report import get_actual_qty_from_bin
#from dairy_erp.customization.sales_invoice.sales_invoice import get_effective_credit

@frappe.whitelist()
def get_items():
	"""Mobile API's common to sell and purchase 
	"""
	item_group = "(" + ",".join([ "'{0}'".format(item.get('name')) for item in frappe.get_all("Item Group", filters=[("Item Group", "name", "!=", "Stationary")]) ]) + ")"
	
	response_dict = frappe.db.sql("""select name as item_code,item_name,description,CAST(is_whole_no AS int) as is_whole_no,
		standard_rate,stock_uom, item_group from `tabItem` where 
		item_group in {0} and is_stock_item=1 and disabled =0 and now() <= end_of_life
		and item_code not in ('Advance Emi','Loan Emi','Milk Incentives')""".format(item_group),as_dict = 1,debug=0)
	for row in response_dict:
		try:
			row.update({"qty": get_item_qty(row.get('item_code')),"uom":frappe.db.sql("select um.uom,um.conversion_factor * i.standard_rate as rate from `tabUOM Conversion Detail` as um join `tabItem` as i on  um.parent = i.name where um.parent = %s",(row.get('item_code')),as_dict=1)})
			# row.get('uom').append({"uom": frappe.db.get_value('Item',row.get('item_code'),'stock_uom'),"rate": frappe.db.get_value('Item',row.get('item_code'), "standard_rate")})
		
		except Exception,e:
			utils.make_mobile_log(title="Sync failed for Master API",method="get_items", status="Error",
			data = row.get('name'), message=e, traceback=frappe.get_traceback())
			response_dict.append({"status": "Error", "message":e, "traceback": frappe.get_traceback()})
	return response_dict


def get_item_qty(item):
	
	user_doc = frappe.get_doc("User",frappe.session.user)
	warehouse = frappe.db.get_value("Village Level Collection Centre",user_doc.company,'warehouse')
	return get_actual_qty_from_bin(item, warehouse)


@frappe.whitelist()
def get_masters():
	#generic: master paramenters as json object,bulk data as app can be in offline mode
	response_dict = {}
	try:
		if frappe.session.user != "Administrator":
			vlcc_details = get_camp_office()
			response_dict.update({
				"items":get_items(),
				# "uom": get_uom(),
				"camp_office": vlcc_details.get('camp_office'),
				"vlcc": vlcc_details.get('name'),
				"farmer": get_farmer(),
				"customer":get_customer(),
				"suppliers": get_supplier(),
				"terms_and_condition": terms_condition(),
				"sales_taxes": taxes_templates(),
				"purchase_taxes":pr_taxes_templates(),
				"diseases": get_diseases(),
				"total_cow_milk": get_milk_attr('COW Milk'),
				"total_buffalo_milk": get_milk_attr('BUFFALO Milk'),
				"farmer_prices": { "items": get_party_item_prices("Farmer") },
				"customer_prices": { "items": get_party_item_prices("Customer") },
				"mi_reference": get_mi_references(),
				"po_reference": get_po_references(),
				"global_percent_effective_credit": frappe.db.get_value("Village Level Collection Centre", \
								vlcc_details.get('name'), 'global_percent_effective_credit'),
				"settings": get_config_settings()
			})
		else:
			frappe.throw(_("User cannot be administrator"))
	except Exception,e:
			utils.make_mobile_log(title="Sync failed Master API",method="get_items", status="Error",
			data = "", message=e, traceback=frappe.get_traceback())
			response_dict.update({"status": "Error", "message":e, "traceback": frappe.get_traceback()})
	return response_dict

def get_party_item_prices(party):
	price_list = guess_price_list(party)
	if price_list:
		return get_item_prices(price_list,party)
	return []

def get_supplier_item_prices(supplier_type):
	price_list = guess_price_list("Supplier", supplier_type)
	if price_list:
		return get_item_prices(price_list)
	return []

def guess_price_list(party_type, supplier_type=None):
	company = frappe.db.get_value("User", frappe.session.user, "company")
	if company:
		if has_common([party_type],["Farmer","Customer"]):
			# Farmer - LFS-{company_name} or GTFS
			# Customer - LCS-{company_name} or GTCS
			price_list_map = {"Farmer": ["LFS-"+company, "GTFS"], "Customer": ["LCS-"+company, "GTCS"]}
			local_price, global_price = price_list_map[party_type]
			if validate_price_list(local_price):
				return local_price
			elif validate_price_list(global_price):
				return global_price
		elif party_type == "Supplier" and supplier_type:
			camp_off = frappe.db.get_value("Village Level Collection Centre",{
				"name": company },"camp_office")
			# dairy supplier - LCOVLCCB-{name} or GTCOVLCCB
			if supplier_type == "VLCC Local":
				if validate_price_list("LVLCCB-"+company):
					return "LVLCCB-"+company
				elif validate_price_list("GTVLCCB"):
					return "GTVLCCB"
			# local (vlcc) supplier - LVLCCB-{name} or GTVLCCB
			elif supplier_type == 'Dairy Type' and camp_off:
				if validate_price_list("LCOVLCCB-"+ camp_off):
					return "LCOVLCCB-"+ camp_off
				elif validate_price_list("GTCOVLCCB"):
					return "GTCOVLCCB"
		return ""


def get_item_list():
	return frappe.db.sql("""select i.name as item_code, i.description, i.item_name,i.item_name,CAST(i.is_whole_no as int) as is_whole_no,
		i.item_group,uom.uom, uom.conversion_factor from `tabItem` i
		left join `tabUOM Conversion Detail` uom
		on uom.parent = i.name where i.is_stock_item = 1
		and i.disabled = 0 and now() <= i.end_of_life and i.item_group != 'Stationary'
		and i.name not in ('Advance Emi','Loan Emi','Milk Incentives') group by i.name, uom.uom""",
	as_dict=True)

def get_item_prices(price_list,party=None):
	""" item prices with per uom rate """
	from operator import itemgetter
	items = get_item_list()
	items_ = {}
	# Fetch item details from VLCC settings
	if party:
		user_doc = frappe.get_doc("User",frappe.session.user)
		vlcc_setting = frappe.get_doc("VLCC Settings",user_doc.company)
		for i in vlcc_setting.vlcc_item:
			if i.get('customer_type') == "Vlcc Local Customer" and party == "Customer":
				items_[i.get('item')] = ""

			if i.get('customer_type') == "Farmer" and party == "Farmer":
				items_[i.get('item')] = ""	

		for i in items:
			item_price = frappe.db.get_value("Item Price", {
				"price_list": price_list,
				"item_code": i.get('item_code')
			}, "price_list_rate") or 0
			if i.get('item_code') in items_:
				uom = [{ 'uom': i.pop('uom'),  'rate': i.pop('conversion_factor') * item_price }]
				i.update({'uom': uom, 'standard_rate': item_price, "qty": get_item_qty(i.get('item_code'))})
				items_[i.get('item_code')] = i
		sorted_items = sorted(items_.values(), key=itemgetter('item_code'), reverse=False)
	else:
		for i in items:
			item_price = frappe.db.get_value("Item Price", {
				"price_list": price_list,
				"item_code": i.get('item_code')
			}, "price_list_rate") or 0
			if i.get('item_code') not in items_:
				uom = [{ 'uom': i.pop('uom'),  'rate': i.pop('conversion_factor') * item_price }]
				i.update({'uom': uom, 'standard_rate': item_price, "qty": get_item_qty(i.get('item_code'))})
				items_[i.get('item_code')] = i
			else:
				items_[i.get('item_code')]['uom'].append({ 'uom':i.get('uom'), 'rate': i.pop('conversion_factor') * item_price })
		sorted_items = sorted(items_.values(), key=itemgetter('item_code'), reverse=False)
	return sorted_items


def get_uom():
	#deprecated current requirement may be future aspect handy
	return frappe.db.sql("select name from `tabUOM`",as_dict=1)


def get_camp_office():
	user_doc = frappe.get_doc("User",frappe.session.user)
	camp_office = frappe.db.get_value("Village Level Collection Centre",user_doc.company,['camp_office','name'],as_dict=1)
	return camp_office


def get_farmer():
	company = get_seesion_company_datails()
	farmer = frappe.db.sql("""
		select name as id,full_name ,vlcc_name, ignore_effective_credit_percent,percent_effective_credit 
	from `tabFarmer` 
	where 
		vlcc_name ='{0}'""".format(company.get('company')),as_dict =1)
	for row in farmer:
		get_net_off(row)
		row.update({"effective_credit": calculate_effective_credit(row.get('id'))})
	return farmer


def get_customer():
	company = get_seesion_company_datails()
	customer = frappe.db.sql("""
						select
							name
						from
							`tabCustomer`
						where
							company = '{0}'
							and customer_group = 'Vlcc Local Institution'
							""".format(company.get('company')),as_dict=1,debug=0)
	return customer

def get_net_off(row):
	#filters are must as it is net off report data retrival
	fliters = {
	"ageing_based_on": "Posting Date",
	"report_date": nowdate(),
	"company": row.get('vlcc_name'),
	"farmer": row.get('id')
	}
	if len(get_data(fliters)):
		row.update({"farmer_net_off": round(get_data(fliters)[0][11],2)})
	else: row.update({"farmer_net_off": 0.00})

def terms_condition():
	return frappe.db.sql("""select name,terms from `tabTerms and Conditions` where vlcc ='{0}'""".format(get_seesion_company_datails().get('company')),as_dict=1)


def get_supplier():
	supplier = frappe.db.sql("""select su.name,su.contact_no, su.supplier_type from `tabSupplier` as su join `tabParty Account` as pa on  pa.parent = su.name where supplier_type in ('VLCC Local','Dairy Type') and pa.company = '{0}'""".format(get_seesion_company_datails().get('company')),as_dict=1)
	for row in supplier:
		row.update({"items": get_supplier_item_prices(row.pop('supplier_type'))})
	return supplier


def taxes_templates():
	taxes_ =  frappe.db.sql(""" select name from `tabSales Taxes and Charges Template` where disabled =0 and company = '{0}'""".format(get_seesion_company_datails().get('company')),as_dict=1)
	for row in taxes_:
		row.update({"template":frappe.db.sql("""select charge_type,description,rate from `tabSales Taxes and Charges` where parent = '{0}'""".format(row.get('name')),as_dict=1)})
	return taxes_


def get_seesion_company_datails():

	user_doc = frappe.get_doc("User",frappe.session.user)
	return {"company" : user_doc.company,"branch_office":user_doc.branch_office,"operator_type":user_doc.operator_type}


def pr_taxes_templates():
	taxes_ =  frappe.db.sql(""" select name from `tabPurchase Taxes and Charges Template` where disabled =0 and company = '{0}'""".format(get_seesion_company_datails().get('company')),as_dict=1)
	for row in taxes_:
		row.update({"template":frappe.db.sql("""select charge_type,description,rate from `tabPurchase Taxes and Charges` where parent = '{0}'""".format(row.get('name')),as_dict=1)})
	return taxes_


def update_supplier_value(row):
	"""supplier item price for different UOM per object """
	
	supplier_item_price = frappe.db.sql("select name from `tabSupplier Item Price` where branch_office = '{0}' and customer = '{1}'".format(row.get('name'),get_seesion_company_datails().get('company')),as_dict=1)
	if supplier_item_price:
		row.update({"items": frappe.db.sql("select item as item_code,item_name,price as standard_rate from `tabSupplier Item Price Child` where parent = '{0}'".format(supplier_item_price[0].get('name')),as_dict=1)})
		for row in row.get('items'):
			#needful UOM respective supplier
			item_ = frappe.db.get_value("Item",row.get('item_code'),['stock_uom','standard_rate','description'],as_dict=1)
			row.update(
				{
					"uom": frappe.db.sql("select um.uom,um.conversion_factor * {0} as rate from `tabUOM Conversion Detail` as um join `tabItem` as i on  um.parent = i.name where um.parent = '{1}'".format(row.get('standard_rate'),row.get('item_code')),as_dict=1),
					"stock_uom": item_.get('stock_uom'),
					"description": item_.get('description'),
					"standard_rate": item_.get('standard_rate')
					
				}
			)
	else:
		row.update({"items":[]})
	


def get_diseases():
	return frappe.db.sql("""select name, description from `tabDisease`""",as_dict=1)


@frappe.whitelist()
def log_out():
	try:
		response_dict = {}
		frappe.local.login_manager.logout()
		frappe.db.commit()
		response_dict.update({"status":"Success", "message":"Successfully Logged Out"})
	except Exception, e:
		response_dict.update({"status":"Error", "error":e, "traceback":frappe.get_traceback()})

	return response_dict

@frappe.whitelist(allow_guest=True)
def forgot_password(user_id):
	try:
		response_dict = {}
		user = frappe.get_doc("User", user_id)
		user.validate_reset_password()
		user.reset_password(send_email=True)
		response_dict.update({"status":"Success", \
			"message":_("Password reset instructions have been sent to your email")})
	except frappe.DoesNotExistError:
		response_dict.update({"status":"Error", "message":_("User {0} does not exist").format(user_id)})
	except Exception, e:
		response_dict.update({"status":"Error", "message":e, "traceback":frappe.get_traceback()})

	return response_dict

def calculate_effective_credit(id_):
	from customization.sales_invoice.sales_invoice import get_effective_credit
	farmer, eff_percent, is_ignore, vlcc = frappe.db.get_value("Farmer", id_ ,['full_name', 'percent_effective_credit', 'ignore_effective_credit_percent', 'vlcc_name'])
	eff_credit = get_effective_credit(farmer)
	percent_eff_credit = 0
	if is_ignore:
		eff_percent = 0
	elif not eff_percent:
		eff_percent = frappe.db.get_value("Village Level Collection Centre",vlcc, "global_percent_effective_credit")
	percent_eff_credit = eff_credit * (eff_percent/100) if eff_percent else eff_credit
	return flt(percent_eff_credit, 2)

def get_milk_attr(item):
	if item:
		user_doc = frappe.get_doc("User",frappe.session.user)
		warehouse = frappe.db.get_value("Village Level Collection Centre",user_doc.company,'warehouse')
		return get_actual_qty_from_bin(item, warehouse)
	else:
		frappe.throw(_("Item Does Not Exist"))


def get_mi_references():
	mr_list = frappe.db.sql("""
			select name,schedule_date,camp_office as supplier
		from 
			`tabMaterial Request` 
		where 
			company = '{0}' and status in ('Ordered','Partially Delivered') and is_dropship =1"""
		.format(get_seesion_company_datails().get('company')),as_dict=1)
	for row in mr_list:
		row.update({
			"items": frappe.db.sql("""
				select item_code,(qty - completed_dn)qty,uom 
			from 
				`tabMaterial Request Item` 
			where
				parent = '{0}'""".format(row.get('name')),as_dict=1)})
	return mr_list


def get_po_references():
	po_list = frappe.db.sql("""
			select name,schedule_date,supplier
		from 
			`tabPurchase Order`
		where 
			status in ('To Receive and Bill') 
			and company = '{0}'""".format(get_seesion_company_datails().get('company')),as_dict=1)
	for row in po_list:
		row.update({
			"items": frappe.db.sql("""
				select item_code,rate,(qty - received_qty) as qty,uom
			from 
				`tabPurchase Order Item` 
			where 
			parent = '{0}'""".format(row.get('name')),as_dict=1)})
	return po_list

def get_config_settings():
	"""
	Fetch allow_negative_effective_credit from VLCC Settings
	"""
	vlcc = frappe.get_doc("User",frappe.session.user).company
	return {
		"allow_negative_eff_credit": frappe.get_doc("VLCC Settings",vlcc).get('allow_negative_effective_credit')
	}