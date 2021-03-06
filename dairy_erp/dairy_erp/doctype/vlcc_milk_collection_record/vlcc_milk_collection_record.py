# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import re
from frappe import _
import json
from frappe.model.document import Document
from frappe.utils.data import add_to_date
from frappe.utils import flt, cstr,nowdate,cint,get_datetime, now_datetime,getdate,get_time
from dairy_erp.customization.manual_loss_gain.loss_gain import handling_loss_gain

class VlccMilkCollectionRecord(Document):

	def validate(self):
		if not self.flags.is_api:
			self.set_posting_date()
			self.validate_duplicate_entry()
			self.validate_status()
			self.validate_route()
			self.validate_vlcc_chilling_centre()
			# self.check_stock()
			self.calculate_amount()

	def on_submit(self):
		try:
			self.validate_status()
			if not self.flags.is_api:
				pr = self.make_purchase_receipt()
				dn = self.make_delivery_note_vlcc()
				pi = self.make_purchase_invoice(pr)
				si = self.make_sales_invoice(dn)
				vmcr_data = self.get_vmcr_data()

				se = handling_loss_gain(vmcr_data.get('data'),
						vmcr_data.get('row'),self)

				frappe.msgprint(_("Delivery Note <b>{0}</b>, Sales Invoice <b>{1}</b> Created at Vlcc level \
					AND Purchase Receipt <b>{2}</b>, Purchase Invoice <b>{3}</b> Created at Chilling centre level{4}".format(
					'<a href="#Form/Delivery Note/'+dn+'">'+dn+'</a>',
					'<a href="#Form/Sales Invoice/'+si+'">'+si+'</a>',
					'<a href="#Form/Purchase Receipt/'+pr+'">'+pr+'</a>',
					'<a href="#Form/Purchase Invoice/'+pi+'">'+pi+'</a>',
					self.get_conditions(se)
				)))
		except Exception as e:
			self.make_dairy_log(title="VMCR Manual Creation",method="manual_vmcr", status="Error",
			data = "data", message=e, traceback=frappe.get_traceback())

	def get_conditions(self,se):
		conditions = ""
		if se and se.get('name'):
			conditions += ", Stock Entry <b>{0}</b> created for HL/CG".format('<a href="#Form/Purchase Invoice/'+se.get('name')+'">'+se.get('name')+'</a>')
		return conditions

	def get_vmcr_data(self):

		data ,row = {},{}
		data.update({
				"shift": self.shift,
				"societyid": self.societyid
			})
		row.update({
				"collectiontime": self.collectiontime,
				"farmerid": self.farmerid,
				"milkquantity": self.milkquantity,
				"milktype": self.milktype,
				"fat": self.fat,
				"snf": self.snf,
				"clr": self.clr,
				"rate": self.rate
			})
		return {"data":data,"row":row}

	def set_posting_date(self):
		self.posting_date = getdate(self.collectiontime)

	def validate_route(self):
		if self.long_format_farmer_id and self.shift == "MORNING":#Created Shrikant 20:00
			farmerid_len = self.long_format_farmer_id.split('_')
			if len(farmerid_len) >= 4 and farmerid_len[2]:
				self.collectionroute = str(farmerid_len[2])
		if self.long_format_farmer_id_e and self.shift == "EVENING":
			farmerid_len = self.long_format_farmer_id_e.split('_')
			if len(farmerid_len) >= 4 and farmerid_len[2]:
				self.collectionroute = str(farmerid_len[2])#End code

		# Add Long Format Society ID to be used in VMCR list view
		self.longsocietyid_listview = self.long_format_farmer_id if self.long_format_farmer_id else \
											self.long_format_farmer_id_e
		self.longsocietyid_listview = self.longsocietyid_listview.split('_')[-1]

		# if self.long_format_farmer_id:
		# 	farmerid_len = self.long_format_farmer_id.split('_')
		# 	if len(farmerid_len) >= 4 and farmerid_len[2]:
		# 		self.collectionroute = str(farmerid_len[2])
				# frappe.throw("The Long Format Farmer Id should be of Format OrgiD_CCID_RouteId_SocietyId")		
		# if self.collectionroute and len(str(self.collectionroute)) < 3:
		# 	frappe.throw("Collection Route contain atleast 3 Charaters")
				
	def validate_duplicate_entry(self):
		if not self.flags.is_api:
			filters = {
				"societyid": self.societyid,
				# "collectiontime": self.collectiontime, #cw commented 13/11
				# "collectiondate": self.collectiondate,
				# "rcvdtime": self.rcvdtime,
				"shift": self.shift,
				"farmerid": self.farmerid,
				"milktype": self.milktype,
				"posting_date":self.posting_date,
				"milk_quality_type":self.milk_quality_type
			}
			is_duplicate = frappe.db.get_value("Vlcc Milk Collection Record", filters, "name")
			if is_duplicate and is_duplicate != self.name:
				frappe.throw(_("""Vlcc Milk Collection Record with shift <b>{0}</b>,
								milktype <b>{1}</b>,Posting Date <b>{2}</b>,Milk Quality Type <b>{3}</b>,Societyid <b>{4}</b>
				is already created""".\
				format(self.shift,self.milktype,getdate(self.posting_date),self.milk_quality_type,self.societyid)))

	def validate_vlcc_chilling_centre(self):
		vlcc_data = frappe.db.get_value("Village Level Collection Centre", {
			"amcu_id": self.farmerid
		}, ["name", "chilling_centre"])

		if vlcc_data:
			vlcc, chilling_centre = vlcc_data[0], vlcc_data[1]
		else:
			frappe.throw(_("Invalid VLCC ID"))

		if not vlcc:
			frappe.throw("Invalid Amcu ID/VLCC")

		# check chilling centre
		address = frappe.db.get_value("Address", {
				"centre_id": self.societyid
			}, "name")
		if not address:
			frappe.throw(_("Invalid Society ID"))

		# check chilling_centre - centre_id
		cc_centre_id = frappe.db.get_value("Address", chilling_centre, "centre_id")
		if self.societyid != cc_centre_id:
			frappe.throw(_("Chilling Centre ID <b>{0}</b> not belongs to VLCC <b>{1}</b>".format(self.societyid, vlcc)))

	def validate_status(self):
		# user only create transactions with status - Accept
		if self.status == "Accept" and (self.milkquantity == 0 or self.rate == 0) and not self.flags.is_api:
			frappe.throw(_("Milk Quantity And Rate Can not be less or equal to zero for Accept Status"))

		if self.status == "Accept" and self.milkquality != 'G' and self.flags.is_api:
			frappe.db.rollback()
			frappe.throw(_("Milk Quality Should be G for Accept Milk"))

		if self.status == "Reject" and self.milkquality not in ['CT','CS','SS'] and self.flags.is_api:
			frappe.db.rollback()
			frappe.throw(_("Milk Quality can be ('CT','CS','SS') for Reject Milk"))

	def check_stock(self):
		"""check stock is available for transactions"""
		if not self.flags.is_api:
			item = self.milktype+" Milk"
			vlcc_warehouse = frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, "warehouse")
			if not vlcc_warehouse:
				frappe.throw(_("Warehouse is not present on VLCC"))
			stock_qty = frappe.db.get_value("Bin", {
				"warehouse": vlcc_warehouse,
				"item_code": item
			},"actual_qty") or 0
			if not stock_qty or stock_qty < self.milkquantity:
				frappe.throw(_("The dispatched quantity of <b>{0}</b> should be less than or \
					equal to stock <b>{1}</b> available at <b>{2}</b> warehouse".format(item, stock_qty, vlcc_warehouse)))

	def calculate_amount(self):
		if self.milkquantity and self.rate:
			if self.milkquality == "SS":
				self.rate = 0
				self.amount = 0
			else:
				self.amount = self.milkquantity * self.rate

	def make_dairy_log(self,**kwargs):
		dlog = frappe.get_doc({"doctype":"Dairy Log"})
		dlog.update({
				"title":kwargs.get("title"),
				"method":kwargs.get("method"),
				"sync_time": now_datetime(),
				"status":kwargs.get("status"),
				"data":json.dumps(kwargs.get("data", "")),
				"error_message":kwargs.get("message", ""),
				"traceback":kwargs.get("traceback", "")
			})
		dlog.insert(ignore_permissions=True)
		frappe.db.commit()
		return dlog.name

	def make_purchase_receipt(self):
		try:
			item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
			camp_office = frappe.db.get_value("Village Level Collection Centre",{"amcu_id":self.farmerid},"camp_office")
			item = frappe.get_doc("Item", item_mapper[self.milktype])
			pr = frappe.new_doc("Purchase Receipt")
			pr.supplier =  frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, "name")
			pr.vlcc_milk_collection_record = self.name
			pr.milk_type = self.milkquality
			pr.company = frappe.db.get_value("Company",{"is_dairy":1},'name')
			pr.camp_office = camp_office
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
					"warehouse": frappe.db.get_value("Address", {"centre_id": self.societyid }, 'warehouse')
				}
			)
			pr.status = "Completed"
			pr.per_billed = 100
			pr.flags.ignore_permissions = True
			pr.submit()
			self.set_posting_datetime(pr)
			self.set_stock_ledger_date(pr)
			return pr.name
		except Exception as e:
			raise e

	def make_delivery_note_vlcc(self):
		try:
			item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
			item = frappe.get_doc("Item", item_mapper[self.milktype])
			customer = frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, "plant_office")
			warehouse = frappe.db.get_value("Village Level Collection Centre", {"amcu_id": self.farmerid }, 'warehouse')
			vlcc = frappe.db.get_value("Village Level Collection Centre", {"amcu_id": self.farmerid }, 'name')
			cost_center = frappe.db.get_value("Cost Center", {"company": vlcc}, 'name')
			dn = frappe.new_doc("Delivery Note")
			dn.customer = customer
			dn.vlcc_milk_collection_record = self.name
			dn.company = vlcc
			dn.append("items",
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
			})
			dn.status = "Completed"
			dn.flags.ignore_permissions = True
			dn.submit()
			self.set_posting_datetime(dn)
			self.set_stock_ledger_date(dn)
			return dn.name
		except Exception as e:
			raise e

	def make_purchase_invoice(self,pr):
		try:
			days = frappe.db.get_singles_dict('Dairy Setting').get('configurable_days') or 0
			item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
			item = frappe.get_doc("Item", item_mapper[self.milktype])
			pi = frappe.new_doc("Purchase Invoice")
			pi.supplier = frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, "name")
			pi.vlcc_milk_collection_record = self.name
			pi.pi_type = "VMCR"
			# pi.due_date = add_to_date(getdate(self.collectiontime),0,0,cint(days))
			pi.company = frappe.db.get_value("Company",{"is_dairy":1},'name')
			pi.append("items",
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"description": item.description,
					"uom": "Litre",
					"qty": self.milkquantity,
					"rate": self.rate,
					"price_list_rate":self.rate,
					"amount": self.amount,
					"warehouse": frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, 'warehouse'),
					"purchase_receipt": pr
				}
			)
			pi.flags.ignore_permissions = True
			pi.flags.for_cc = True
			pi.submit()
			self.set_posting_datetime(pi,days)
			return pi.name
		except Exception as e:
			raise e

	def make_sales_invoice(self, dn):
		try:
			days = frappe.db.get_value("VLCC Settings", self.associated_vlcc, 'configurable_days') or 0
			item_mapper = {"COW": "COW Milk", "BUFFALO": "BUFFALO Milk"}
			item = frappe.get_doc("Item", item_mapper[self.milktype])
			customer = frappe.db.get_value("Village Level Collection Centre", {"amcu_id":self.farmerid}, "plant_office")
			warehouse = frappe.db.get_value("Village Level Collection Centre", {"amcu_id": self.farmerid }, 'warehouse')
			vlcc = frappe.db.get_value("Village Level Collection Centre", {"amcu_id": self.farmerid }, 'name')
			cost_center = frappe.db.get_value("Cost Center", {"company": vlcc}, 'name')
			si = frappe.new_doc("Sales Invoice")
			si.customer = customer
			si.company = vlcc
			# si.due_date = add_to_date(getdate(self.collectiontime),0,0,cint(days))
			si.vlcc_milk_collection_record = self.name
			si.append("items",
			{
				"item_code": item.item_code,
				"qty": self.milkquantity,
				"rate": self.rate,
				"price_list_rate":self.rate,
				"amount": self.amount,
				"warehouse": warehouse,
				"cost_center": cost_center,
				"delivery_note": dn
			})
			si.flags.ignore_permissions = True
			si.submit()
			self.set_posting_datetime(si,days)
			return si.name
		except Exception as e:
			raise e

	def set_posting_datetime(self,doc,days=None):
		if self.collectiontime:			
			frappe.db.sql("""update `tab{0}` 
				set 
					posting_date = '{1}',posting_time = '{2}'
				where 
					name = '{3}'""".format(doc.doctype,getdate(self.collectiontime),
						get_time(self.collectiontime),doc.name))
			if doc.doctype in ['Sales Invoice','Purchase Invoice']:
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