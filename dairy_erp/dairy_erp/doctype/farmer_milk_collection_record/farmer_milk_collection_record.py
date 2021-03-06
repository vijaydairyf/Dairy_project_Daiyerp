# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import add_to_date
from frappe.utils import flt, cstr,nowdate,cint,get_datetime, now_datetime,getdate,get_time

class FarmerMilkCollectionRecord(Document):

	def validate(self):
		self.create_milk_item()
		self.make_uom_config()
		self.validate_status()
		self.validate_duplicate_entry()
		self.validate_society_id()
		self.check_valid_farmer()
		self.set_posting_date()

	def on_submit(self):
		try:
			if self.status == "Accept" and not self.flags.is_api:
				pr = self.purchase_receipt()
				pi = self.purchase_invoice(pr)
				frappe.msgprint(_("Purchase Receipt <b>{0}</b>, Purchase Invoice <b>{1}</b> Created".format(
					'<a href="#Form/Purchase Receipt/'+pr+'">'+pr+'</a>',
					'<a href="#Form/Purchase Invoice/'+pi+'">'+pi+'</a>',
				)))
		except Exception as e:
			print frappe.get_traceback()
			frappe.db.rollback()
			frappe.throw(e)

	def set_posting_date(self):
		self.posting_date = getdate(self.collectiontime)

	def create_milk_item(self):
		if self.milktype and not frappe.db.exists('Item', self.milktype + " Milk"):
			item = frappe.new_doc("Item")
			item.item_code = self.milktype + " Milk"
			item.item_group = "Milk & Products"
			item.weight_uom = "Litre"
			item.is_stock_item = 1
			item.insert()

	def make_uom_config(self):
		uom_obj = frappe.get_doc("UOM","Nos")
		uom_obj.must_be_whole_number = 0
		uom_obj.save()

	def validate_duplicate_entry(self):
		if not self.flags.is_api:
			is_duplicate = frappe.db.get_value(self.doctype, {
				"societyid": self.societyid,
				"collectiontime": self.collectiontime,
				"collectiondate": self.collectiondate,
				"rcvdtime": self.rcvdtime,
				"shift": self.shift,
				"farmerid": self.farmerid,
				"milktype": self.milktype
			}, "name")
			if is_duplicate and is_duplicate != self.name:
				frappe.throw(_("Duplicate Entry found - {0}".format(is_duplicate)))

	def validate_society_id(self):
		if not self.associated_vlcc:
			frappe.throw(_("Please select Associated Vlcc"))
		vlcc = frappe.db.exists("Village Level Collection Centre", self.associated_vlcc)
		societyid = frappe.db.get_value("Village Level Collection Centre", {"amcu_id": self.societyid}, "name")
		if not vlcc or not societyid:
			frappe.throw(_("Vlcc does not exist!"))

	def check_valid_farmer(self):
		is_valide_farmer = frappe.db.get_value("Farmer",{"vlcc_name": self.associated_vlcc,"name":self.farmerid },'name')
		if not is_valide_farmer:
			frappe.throw(_("Invalid Farmer {0}".format(self.farmerid)))

	def validate_status(self):
		# user only create transactions with status - Accept
		if self.status == "Reject":
			frappe.throw(_("Status is Reject, Transaction can not be created"))

	def purchase_receipt(self):
		# purchase receipt against VLCC
		item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
		item = frappe.get_doc("Item", item_mapper[self.milktype])
		cost_center = frappe.db.get_value("Cost Center", {"company": self.associated_vlcc }, 'name')
		warehouse = frappe.db.get_value("Village Level Collection Centre",self.associated_vlcc, 'warehouse')
		pr = frappe.new_doc("Purchase Receipt")
		pr.farmer_milk_collection_record = self.name
		pr.supplier =  frappe.db.get_value("Supplier", { "farmer": self.farmerid }, "name")
		pr.company = self.associated_vlcc
		pr.buying_price_list = "Standard Buying"
		pr.append("items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"uom": "Litre",
				"qty": self.milkquantity,
				"rate": self.rate,
				"price_list_rate": self.rate,
				"amount": self.amount,
				"warehouse": warehouse,
				"cost_center": cost_center
			}
		)
		pr.status = "Completed"
		pr.per_billed = 100
		pr.flags.ignore_permissions = True
		pr.flags.ignore_material_price = True
		pr.submit()
		self.set_posting_datetime(pr)
		self.set_stock_ledger_date(pr)
		return pr.name

	def purchase_invoice(self, pr):
		# purchase invoice against farmer
		item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
		days = frappe.db.get_value('VLCC Settings',{'vlcc':self.associated_vlcc},'configurable_days') or 0
		item = frappe.get_doc("Item", item_mapper[self.milktype])
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier =  frappe.db.get_value("Supplier", {"farmer": self.farmerid}, "name")
		pi.farmer_milk_collection_record = self.name
		# pi.due_date = add_to_date(getdate(self.collectiontime),0,0,cint(days))
		pi.company = self.associated_vlcc
		pi.buying_price_list = "Standard Buying"
		pi.append("items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"uom": "Litre",
				"qty": self.milkquantity,
				"rate": self.rate,
				"amount": self.amount,
				"warehouse": frappe.db.get_value("Village Level Collection Centre", self.associated_vlcc, 'warehouse'),
				"purchase_receipt": pr
			}
		)
		pi.flags.ignore_permissions = True
		pi.flags.ignore_material_price = True
		pi.submit()
		self.set_posting_datetime(pi,days)
		return pi.name

	def set_posting_datetime(self,doc,days=None):
		if self.collectiontime:			
			frappe.db.sql("""update `tab{0}` 
				set 
					posting_date = '{1}',posting_time = '{2}'
				where 
					name = '{3}'""".format(doc.doctype,getdate(self.collectiontime),
						get_time(self.collectiontime),doc.name))

			if doc.doctype == 'Purchase Invoice':
				frappe.db.sql("""update `tab{0}` 
					set 
						due_date = '{1}'
					where 
						name = '{2}'""".format(doc.doctype,add_to_date(getdate(self.collectiontime),0,0,cint(days)),doc.name))
			frappe.db.sql("""update `tabGL Entry` 
					set 
						posting_date = %s
					where 
						voucher_no = %s""",(getdate(self.collectiontime),doc.name))


	def set_stock_ledger_date(self,doc):
		if self.collectiontime:
			frappe.db.sql("""update `tabStock Ledger Entry` 
					set 
						posting_date = %s
					where 
						voucher_no = %s""",(getdate(self.collectiontime),doc.name))