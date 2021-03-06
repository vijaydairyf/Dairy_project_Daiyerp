# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from dairy_erp.dairy_utils import make_dairy_log, make_journal_entry
from frappe.utils import flt, cstr,nowdate,cint
import json

class FarmerPaymentCycleReport(Document):
	
	def validate(self):
		if frappe.db.get_value("Farmer Payment Cycle Report",{'cycle':self.cycle,\
			 'vlcc_name':self.vlcc_name, 'farmer_id':self.farmer_id},'name') and self.is_new():
			frappe.throw(_("FPCR has already been generated for this cycle against farmer <b>{0}</b>".format(self.farmer_id)))
		if self.collection_to >= nowdate() :
			frappe.throw(_("You can generate FPCR after <b>'{0}'</b>".format(self.collection_to)))
		
	
	def before_submit(self):
		try:
			self.advance_operation()
			self.loan_operation()
			self.update_fpcr()
			if float(self.incentives) != 0:
				if not frappe.db.get_value("Purchase Invoice", {'cycle':self.cycle,\
			 'supplier': self.farmer_name},'name'):
					self.create_incentive()
					frappe.msgprint(_("Purchase invoice created successfully against Incentives"))
				else: frappe.msgprint(_("Purchase invoice Already created successfully against Incentives"))
		except Exception,e:
			frappe.db.rollback()
			make_dairy_log(title="JV creation Against Advance Failed",method="make_jv", status="Error",
				data = "data", message=e, traceback=frappe.get_traceback())		
			frappe.throw("Something Went Wrong Please check dairy log")
					
	def update_fpcr(self):
		loan_total, loan_je, adavnce_je, advance_total = 0, 0, 0, 0 
		for row in self.loan_child:
			je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.loan_id,'type':'Farmer Loan'})
			loan_je += je_amt[0].get('amt')
			loan_total += row.principle
		for row in self.advance_child:
			je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.adv_id,'type':'Farmer Advance'})
			adavnce_je += je_amt[0].get('amt')
			advance_total += row.principle
		self.advance_outstanding = float(advance_total) - float(adavnce_je)
		self.loan_outstanding = float(loan_total) - float(loan_je)
	
	
	def advance_operation(self):
		flag, je = False, ""
		for row in self.advance_child:
			flag = True
			# SG 5-10
			je_exist = frappe.db.get_value("Journal Entry",{'cycle': self.cycle,\
						'farmer_advance':row.adv_id,'type':'Farmer Advance'}, 'name')
			if not je_exist:
				self.validate_advance(row)
				je = self.create_advance_je(row)
				self.update_advance_doc(row, je)
			elif je_exist:
				self.update_je_for_advance(row, self.cycle, je_exist)
				self.update_advance_after_fpcr(row)
		if flag:
			frappe.msgprint(_("Journal Entry created successfully against Advances"))
	
	def loan_operation(self):
		flag = False
		for row in self.loan_child:
			flag = True
			je_exist = frappe.db.get_value("Journal Entry",{'cycle': self.cycle,\
						'farmer_advance':row.loan_id,'type':'Farmer Loan'}, 'name')
			if not je_exist:
				self.validate_loan(row)
				je = self.create_loan_je(row)
				self.update_loan_doc(row, je)
			elif je_exist:
				self.update_je_for_loan(row, self.cycle, je_exist)
				self.update_loan_after_fpcr(row)
		if flag:
			frappe.msgprint(_("Journal Entry created successfully against Loans"))

	
	def validate_advance(self, row):
		adv_doc = frappe.get_doc("Farmer Advance",row.adv_id)
		if not row.amount:
			frappe.throw(_("Please Enter amount against <b>{0}</b>".format(row.adv_id)))
		if float(row.amount) > float(row.outstanding):
			frappe.throw(_("Amount can not be greater than  outstanding for <b>{0}</b>".format(row.adv_id)))
		if (int(row.no_of_instalment) + int(adv_doc.extension)) - row.paid_instalment == 1 and \
			(float(row.amount) < float(adv_doc.emi_amount) or float(row.outstanding) != float(adv_doc.emi_amount)):
			frappe.throw(_("Please Use Extension for <b>{0}</b>".format(row.adv_id)))
	
	
	def validate_loan(self, row):
		loan_doc = frappe.get_doc("Farmer Loan",row.loan_id)
		if not row.amount:
			frappe.throw(_("Please Enter amount against <b>{0}</b>".format(row.loan_id)))
		if float(row.amount) > float(row.outstanding):
			frappe.throw(_("Amount can not be greater than  outstanding for <b>{0}</b>".format(row.loan_id)))
		if (int(row.no_of_instalment) + int(loan_doc.extension)) - loan_doc.paid_instalment == 1 and \
			(float(row.amount) < float(loan_doc.emi_amount) or float(row.outstanding) != float(loan_doc.emi_amount)):
			frappe.throw(_("Please Use Extension <b>{0}</b>".format(row.loan_id)))

	def update_loan_doc(self, row, je = None):
		instalment = 0
		principal_interest = get_interest_amount(row.amount, row.loan_id)
		je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.loan_id,'type':'Farmer Loan'})
		
		loan_doc = frappe.get_doc("Farmer Loan", row.loan_id)
		loan_doc.total_principle_paid = principal_interest.get('principal')
		loan_doc.total_interest_paid = principal_interest.get('interest')
		loan_doc.last_extension_used = flt(loan_doc.extension)
		loan_doc.append("cycle", {"cycle": self.cycle, "sales_invoice": je})
		loan_doc.outstanding_amount = float(loan_doc.advance_amount) - je_amt[0].get('amt')
		for i in loan_doc.cycle:
			instalment += 1
		loan_doc.paid_instalment = instalment
		if loan_doc.outstanding_amount > 0:
			loan_doc.emi_amount = (float(loan_doc.outstanding_amount)) / (float(loan_doc.no_of_instalments) + float(loan_doc.extension) - float(loan_doc.paid_instalment))
		if loan_doc.outstanding_amount == 0:
			loan_doc.status = "Paid"
			loan_doc.emi_amount = 0
		loan_doc.flags.ignore_permissions = True
		loan_doc.save()

	def create_loan_je(self, row): # SG-8-10
		principal_interest = get_interest_amount(row.amount, row.loan_id)
		je_doc = make_journal_entry(voucher_type = "Journal Entry",company = self.vlcc_name,
			posting_date = nowdate(),debit_account = "Debtors - ",credit_account = "Loans and Advances - ", 
			type = "Farmer Loan", cycle = self.cycle, amount = principal_interest.get('principal'), 
			party_type = "Customer", party = self.farmer_name, master_no = row.loan_id,
			interest_account = "Interest Income - ", interest_amount= principal_interest.get('interest'))

		frappe.db.set_value("Journal Entry", je_doc.name, 'posting_date', self.collection_to)

		company_abbr = frappe.db.get_value("Company",get_vlcc(),'abbr',as_dict=1)
		frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr.get('abbr'), "voucher_no": je_doc.name},\
					'posting_date', self.collection_to )
		frappe.db.set_value("GL Entry", {"account": 'Loans and Advances - '+company_abbr.get('abbr'), "voucher_no": je_doc.name},\
					'posting_date', self.collection_to )
		frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr.get('abbr'), "voucher_no": je_doc.name},\
						'posting_date', self.collection_to )
		
		return je_doc.name

	def create_advance_je(self, row): # SG-5-10
		advance_type = frappe.db.get_value("Farmer Advance",{'name': row.adv_id}, 'advance_type')
		if advance_type == "Money Advance":
			je_doc = make_journal_entry(voucher_type = "Journal Entry",company = self.vlcc_name,
        			posting_date = nowdate(),debit_account = "Debtors - ",credit_account = "Loans and Advances - ", 
        			type = "Farmer Advance", cycle = self.cycle, amount = row.amount, faf_flag = 0,
        			party_type = "Customer", party = self.farmer_name, master_no = row.adv_id, advance_type = advance_type)
			frappe.db.set_value("Journal Entry", je_doc.name, 'posting_date', self.collection_to)

			company_abbr = frappe.db.get_value("Company",get_vlcc(),'abbr')
			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_doc.name},\
						'posting_date', self.collection_to )
			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_doc.name},\
						'posting_date', self.collection_to )
			return je_doc.name

		if advance_type == "Feed And Fodder Advance":
			# parameter 'faf_flag', is used to fetch data on net-payOff report.
			je_doc = make_journal_entry(voucher_type = "Journal Entry",company = self.vlcc_name,
        			posting_date = nowdate(),debit_account = "Debtors - ",credit_account = "Feed And Fodder Advance - ", 
        			type = "Farmer Advance", cycle = self.cycle, amount = row.amount, faf_flag = 1,
        			party_type = "Customer", party = self.farmer_name, master_no = row.adv_id, advance_type = advance_type)
			frappe.db.set_value("Journal Entry", je_doc.name, 'posting_date', self.collection_to)

			company_abbr = frappe.db.get_value("Company",get_vlcc(),'abbr')
			frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_doc.name},\
						'posting_date', self.collection_to )
			frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_doc.name},\
						'posting_date', self.collection_to )
			return je_doc.name

	def update_advance_doc(self, row, je=None):	# SG-5-10
		instalment = 0
		je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.adv_id,'type':'Farmer Advance'})
		adv_doc = frappe.get_doc("Farmer Advance", row.adv_id)
		adv_doc.append("cycle", {"cycle": self.cycle, "sales_invoice": je})
		adv_doc.outstanding_amount = float(adv_doc.advance_amount) - je_amt[0].get('amt')
		for i in adv_doc.cycle:
			instalment +=1
		adv_doc.paid_instalment = instalment
		adv_doc.fpcr_instalment = instalment
		if adv_doc.outstanding_amount > 0 :
			adv_doc.emi_amount = (float(adv_doc.outstanding_amount)) / (float(adv_doc.no_of_instalment) + float(adv_doc.extension) - float(adv_doc.paid_instalment))
		if adv_doc.outstanding_amount == 0:
			adv_doc.status = "Paid"
			adv_doc.emi_amount = 0
		adv_doc.flags.ignore_permissions =True
		adv_doc.save()

	def update_advance_after_fpcr(self, row):	# SG-5-10
		instalment = 0
		je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.adv_id,'type':'Farmer Advance'})
		adv_doc = frappe.get_doc("Farmer Advance", row.adv_id)
		adv_doc.outstanding_amount = float(adv_doc.advance_amount) - je_amt[0].get('amt')
		for i in adv_doc.cycle:
			instalment +=1
		adv_doc.paid_instalment = instalment
		adv_doc.fpcr_instalment = instalment
		if adv_doc.outstanding_amount > 0 :
			adv_doc.emi_amount = (float(adv_doc.outstanding_amount)) / (float(adv_doc.no_of_instalment) + float(adv_doc.extension) - float(adv_doc.paid_instalment))
		if adv_doc.outstanding_amount == 0:
			adv_doc.status = "Paid"
			adv_doc.emi_amount = 0
		adv_doc.flags.ignore_permissions =True
		adv_doc.save()

	def update_loan_after_fpcr(self, row):
		principal_interest = get_interest_amount(row.amount, row.loan_id)
		print principal_interest,"inside update_loan_after_fpcr\n\n\n\n"
		instalment = 0
		je_amt = frappe.get_all("Journal Entry",fields=['ifnull(sum(total_debit), 0) as amt']\
			,filters={'farmer_advance':row.loan_id,'type':'Farmer Loan'})
		
		loan_doc = frappe.get_doc("Farmer Loan", row.loan_id)
		loan_doc.total_principle_paid = principal_interest.get('principal')
		loan_doc.total_interest_paid = principal_interest.get('interest')
		loan_doc.last_extension_used = flt(loan_doc.extension)
		loan_doc.outstanding_amount = float(loan_doc.advance_amount) - je_amt[0].get('amt')
		for i in loan_doc.cycle:
			instalment += 1
		loan_doc.paid_instalment = instalment
		if loan_doc.outstanding_amount > 0:
			loan_doc.emi_amount = (float(loan_doc.outstanding_amount)) / (float(loan_doc.no_of_instalments) + float(loan_doc.extension) - float(loan_doc.paid_instalment))
		if loan_doc.outstanding_amount == 0:
			loan_doc.status = "Paid"
			loan_doc.emi_amount = 0
		loan_doc.flags.ignore_permissions = True
		loan_doc.save()

	def update_je_for_loan(self, row, cycle, je_no):	# SG-5-10
		principal_interest = get_interest_amount(row.amount, row.loan_id)
		company = frappe.db.get_value("Company",self.vlcc_name,['name','abbr','cost_center'],as_dict=1)
		accounts_row = frappe.db.get_value("Journal Entry Account", {'parent':je_no}, 'name')
		accounts_row_debit = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
			'Debtors - '+company.get('abbr')}, 'name')

		accounts_row_credit_principal = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
			'Loans and Advances - '+company.get('abbr')}, 'name')

		accounts_row_credit_interest = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
			'Interest Income - '+company.get('abbr')}, 'name')

		frappe.db.set_value("Journal Entry Account",{'name':accounts_row_debit, 'account':"Debtors - "+company.get('abbr')}, 'debit_in_account_currency', principal_interest.get('principal')+principal_interest.get('interest'))
		frappe.db.set_value("Journal Entry Account",{'name':accounts_row_credit_principal, 'account':"Loans and Advances - "+company.get('abbr')}, 'credit_in_account_currency', principal_interest.get('principal'))
		frappe.db.set_value("Journal Entry Account",{'name':accounts_row_credit_interest, 'account':"Interest Income - "+company.get('abbr')}, 'credit_in_account_currency', principal_interest.get('interest'))
		frappe.db.set_value("Journal Entry", je_no, 'total_credit', row.amount)
		frappe.db.set_value("Journal Entry", je_no, 'total_debit', row.amount)
		frappe.db.set_value("Journal Entry", je_no, 'posting_date', self.collection_to)
		self.update_gl_entry_loan(je_no, principal_interest)

	def update_je_for_advance(self, row, cycle, je_no):	# SG-5-10
		company = frappe.db.get_value("Company",self.vlcc_name,['name','abbr','cost_center'],as_dict=1)
		advance_type = frappe.db.get_value("Farmer Advance",{'name': row.adv_id}, 'advance_type')
		if advance_type == "Money Advance":
			accounts_row_debit = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
				'Debtors - '+company.get('abbr')}, 'name')

			accounts_row_credit = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
				'Loans and Advances - '+company.get('abbr')}, 'name')

			frappe.db.set_value("Journal Entry Account",{'name':accounts_row_debit, 'account':'Debtors - '+company.get('abbr')}, 'debit_in_account_currency', row.amount)
			frappe.db.set_value("Journal Entry Account",{'name':accounts_row_credit, 'account':'Loans and Advances - '+company.get('abbr')}, 'credit_in_account_currency', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'total_credit', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'total_debit', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'posting_date', self.collection_to)
			self.update_gl_entry_advance(je_no, row, row.amount)

		if advance_type == "Feed And Fodder Advance":
			accounts_row_debit = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
				'Debtors - '+company.get('abbr')}, 'name')

			accounts_row_credit = frappe.db.get_value("Journal Entry Account", {'parent':je_no,"account":\
				'Feed And Fodder Advance - '+company.get('abbr')}, 'name')
			
			frappe.db.set_value("Journal Entry Account",{'name':accounts_row_debit, 'account':'Debtors - '+company.get('abbr')}, 'debit_in_account_currency', row.amount)
			frappe.db.set_value("Journal Entry Account",{'name':accounts_row_credit, 'account':'Feed And Fodder Advance - '+company.get('abbr')}, 'credit_in_account_currency', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'total_credit', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'total_debit', row.amount)
			frappe.db.set_value("Journal Entry", je_no, 'posting_date', self.collection_to)
			self.update_gl_entry_advance(je_no, row, row.amount)

	def update_gl_entry_loan(self, je_no, principal_interest):
		if je_no and principal_interest:
			company_abbr = frappe.db.get_value("Company",get_vlcc(),'abbr')

			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
						'debit',  principal_interest.get('principal') + principal_interest.get('interest'))
			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
						'credit',  0)
			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
						'debit_in_account_currency',  principal_interest.get('principal') + principal_interest.get('interest'))
			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
						'credit_in_account_currency', 0)
			frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
						'posting_date', self.collection_to )

			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
						'posting_date', self.collection_to )
			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
						'debit', 0)
			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
						'credit', principal_interest.get('principal'))
			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
						'debit_in_account_currency', 0)
			frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
						'credit_in_account_currency', principal_interest.get('principal'))

			frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr, "voucher_no": je_no},\
						'debit', 0)
			frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr, "voucher_no": je_no},\
						'credit', principal_interest.get('interest') )
			frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr, "voucher_no": je_no},\
						'debit_in_account_currency', 0)
			frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr, "voucher_no": je_no},\
						'credit_in_account_currency', principal_interest.get('interest'))
			frappe.db.set_value("GL Entry", {"account":"Interest Income - "+company_abbr, "voucher_no": je_no},\
						'posting_date', self.collection_to )

	def update_gl_entry_advance(self, je_no, row, amount):
		if je_no and amount:
			advance_type = frappe.db.get_value("Farmer Advance",{'name': row.adv_id}, 'advance_type')
			company_abbr = frappe.db.get_value("Company",get_vlcc(),'abbr')
			if advance_type == "Money Advance":
				frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
							'debit', amount)
				frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
							'credit_in_account_currency', 0)
				frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
							'debit_in_account_currency', amount)
				frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
							'credit_in_account_currency', 0)
				frappe.db.set_value("GL Entry", {"account": "Debtors - "+company_abbr, "voucher_no": je_no},\
							'posting_date', self.collection_to )

				frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
							'debit', 0)
				frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
							'credit', amount )
				frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
							'debit_in_account_currency', 0)
				frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
							'credit_in_account_currency', amount )
				frappe.db.set_value("GL Entry", {"account": "Loans and Advances - "+company_abbr, "voucher_no": je_no},\
							'posting_date', self.collection_to )
				

			if advance_type == "Feed And Fodder Advance":
				frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_no},\
							'debit', amount )
				frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_no},\
							'credit', 0 )
				frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_no},\
							'debit_in_account_currency', amount )
				frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_no},\
							'credit_in_account_currency', 0 )
				frappe.db.set_value("GL Entry", {"account": 'Debtors - '+company_abbr, "voucher_no": je_no},\
							'posting_date', self.collection_to )

				frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_no},\
							'debit', 0 )
				frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_no},\
							'credit', amount )
				frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_no},\
							'debit_in_account_currency', 0 )
				frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_no},\
							'credit_in_account_currency', amount )
				frappe.db.set_value("GL Entry", {"account": 'Feed And Fodder Advance - '+company_abbr, "voucher_no": je_no},\
							'posting_date', self.collection_to )

	def create_incentive(self):
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = self.farmer_name
		pi.company = self.vlcc_name
		pi.pi_type = "Incentive"
		pi.cycle = self.cycle
		pi.append("items",
			{
				"qty":1,
				"item_code": "Milk Incentives",
				"rate": self.incentives,
				"amount": self.incentives,
				"cost_center": frappe.db.get_value("Company", self.vlcc_name, "cost_center")
			})
		pi.flags.ignore_permissions = True
		pi.save()
		pi.submit()
		
		#updating date for current cycle
		frappe.db.set_value("Purchase Invoice", pi.name, 'posting_date', self.collection_to)
		gl_stock = frappe.db.get_value("Company", get_vlcc(), 'stock_received_but_not_billed')
		gl_credit = frappe.db.get_value("Company", get_vlcc(), 'default_payable_account')
		frappe.db.set_value("GL Entry",{'account': gl_stock,'voucher_no':pi.name}, 'posting_date', self.collection_to)
		frappe.db.set_value("GL Entry",{'account': gl_credit,'voucher_no':pi.name}, 'posting_date', self.collection_to)

def get_interest_amount(amount, data):
	loan_doc = frappe.get_all("Farmer Loan",fields=['interest','no_of_instalments','emi_amount'],filters={'name':data})
	interest_per_cycle = loan_doc[0].get('interest') / loan_doc[0].get('no_of_instalments')
	principal_per_cycle = amount - interest_per_cycle
	if amount <= interest_per_cycle:
		interest_per_cycle = flt(amount,2)
		principal_per_cycle = 0
	else:
		interest_per_cycle = flt(interest_per_cycle,2)
		principal_per_cycle = flt((amount - interest_per_cycle),2)
	return { 'interest': interest_per_cycle , 'principal': principal_per_cycle}

@frappe.whitelist()
def get_fmcr(start_date, end_date, vlcc, farmer_id, cycle=None):
	fmcr =  frappe.db.sql("""
			select rcvdtime,shift,milkquantity,fat,snf,rate,amount
		from 
			`tabFarmer Milk Collection Record`
		where 
			associated_vlcc = '{0}' and date(rcvdtime) between '{1}' and '{2}' and farmerid= '{3}'
			""".format(vlcc, start_date, end_date, farmer_id),as_dict=1)
	amount = 0
	qty = 0
	for i in fmcr:
		amount += i.get('amount')
		qty += i.get('milkquantity')
	
	amount = flt(amount,2)
	return {
		"fmcr":fmcr,
		"weighted_data" : get_weighted_fmcr_data(fmcr), # Added by Niraj
		"incentive": get_incentives(amount, qty, vlcc) or 0, 
		"advance": get_advances(start_date, end_date, vlcc, farmer_id, cycle) or 0,
		"loan": get_loans(start_date, end_date, vlcc, farmer_id, cycle) or 0,
		"fodder": get_fodder_amount(start_date, end_date, farmer_id, vlcc) or 0,
		"vet": vet_service_amnt(start_date, end_date, farmer_id, vlcc) or 0,
		"child_loan": get_loans_child(start_date, end_date, vlcc, farmer_id,cycle),
		"child_advance": get_advance_child(start_date, end_date, vlcc, farmer_id, cycle)
	}

def get_weighted_fmcr_data(fmcr_data):
	if len(fmcr_data) == 0:
		return
	milkquantity, fat, snf, rate, amount = 0, 0, 0, 0, 0

	for data in fmcr_data:
		milkquantity += data.get('milkquantity')
		fat += data.get('fat')*data.get('milkquantity')
		snf += data.get('snf')*data.get('milkquantity') 
		rate += data.get('rate')*data.get('milkquantity')
		amount += data.get('amount')

	fat, snf , rate = round(fat/milkquantity, 2), round(snf/milkquantity, 2), round(rate/milkquantity, 2)

	return {
		"milkquantity" : milkquantity,
		"fat" : fat,
		"snf" : snf,
		"rate": rate,
		"amount" : amount
	}

def get_incentives(amount, qty, vlcc=None):
	if vlcc and amount and qty:
		incentive = 0
		name = frappe.db.get_value("Farmer Settings", {'vlcc':vlcc}, 'name')
		farmer_settings = frappe.get_doc("Farmer Settings",name)
		if farmer_settings.enable_local_setting and not farmer_settings.enable_local_per_litre:
			incentive = (float(farmer_settings.local_farmer_incentive ) * float(amount)) / 100	
		if farmer_settings.enable_local_setting and farmer_settings.enable_local_per_litre:
			incentive = (float(farmer_settings.local_per_litre) * float(qty))
		if not farmer_settings.enable_local_setting and not farmer_settings.enable_per_litre:
			incentive = (float(farmer_settings.farmer_incentives) * float(amount)) / 100
		if not farmer_settings.enable_local_setting and farmer_settings.enable_per_litre:
			incentive = (float(farmer_settings.per_litre) * float(qty))
		return incentive


@frappe.whitelist()
def get_advances(start_date, end_date, vlcc, farmer_id, cycle = None):
	
	advance  = frappe.db.sql("""
			select ifnull(sum(outstanding_amount),0) as oustanding
		from 
			`tabFarmer Advance` 
		where
			creation < now() and  farmer_id = '{2}' and status = 'Unpaid' and docstatus = 1
		 """.format(start_date, end_date, farmer_id), as_dict=1)
	if len(advance):
		return advance[0].get('oustanding') if advance[0].get('oustanding') != None else 0
	else: return 0


@frappe.whitelist()
def get_loans(start_date, end_date, vlcc, farmer_id, cycle = None):

	loan  = frappe.db.sql("""
			select ifnull(sum(outstanding_amount),0) as oustanding
		from 
			`tabFarmer Loan` 
		where
			creation < now() and  farmer_id = '{2}' and status = 'Unpaid' and docstatus = 1
		 """.format(start_date, end_date, farmer_id), as_dict=1)
	if len(loan):
		return loan[0].get('oustanding') if loan[0].get('oustanding') != None else 0
	else: return 0


def get_fodder_amount(start_date, end_date, farmer_id, vlcc=None):
	
	fodder = frappe.db.sql("""
			select ifnull(sum(si.amount),0) as amt 
		from 
			`tabSales Invoice Item` si,
			`tabSales Invoice` s 
		where 
			s.name= si.parent and 
			s.docstatus = 1 and
			si.item_group in ('Cattle Feed') and s.local_sale = 1  and 
			s.farmer = '{0}'and
			s.local_sale_type not in ('Feed And Fodder Advance') and 
			s.posting_date between '{1}' and '{2}'
			""".format(farmer_id, start_date, end_date),as_dict=1)
	if len(fodder):
		return fodder[0].get('amt') if fodder[0].get('amt') != None else 0
	else: return 0


def vet_service_amnt(start_date, end_date, farmer_id, vlcc=None): 
	
	vet_amnt = frappe.db.sql("""
			select ifnull(sum(si.amount),0) as amt 
		from 
			`tabSales Invoice Item` si,
			`tabSales Invoice` s 
		where 
			s.name= si.parent and 
			s.docstatus = 1 and
			si.item_group in ('Veterinary Services') and s.service_note = 1  and 
			s.farmer = '{0}'and
			s.posting_date between '{1}' and '{2}'
			""".format(farmer_id, start_date, end_date),as_dict=1)
	if len(vet_amnt):
		return vet_amnt[0].get('amt') if vet_amnt[0].get('amt') != None else 0
	else: return 0


# @frappe.whitelist()
# def get_cycle(doctype,text,searchfields,start,pagelen,filters):
# 	return frappe.db.sql("""
# 			select name 
# 		from
# 			`tabFarmer Date Computation`
# 		where
# 			 end_date < now() and vlcc = '{vlcc}' and name like '{txt}' and name not in (select cycle from `tabFarmer Payment Cycle Report` where farmer_id = '{farmer}')
# 		""".format(farmer = filters.get('farmer') , vlcc = filters.get('vlcc'),txt= "%%%s%%" % text,as_list=True))

@frappe.whitelist()
def get_cycle(doctype,text,searchfields,start,pagelen,filters):
	return frappe.db.sql("""
			select name 
		from
			`tabFarmer Date Computation`
		where
			end_date < now() and 
			end_date >= (select 
			 				date(creation) 
			 			from 
			 				`tabFarmer` 
			 			where 
			 				farmer_id='{farmer}') and 
			vlcc = '{vlcc}' and 
			name like '{txt}' and 
			name not in (select 
							cycle 
						from 
							`tabFarmer Payment Cycle Report` 
						where 
							farmer_id = '{farmer}')
		""".format(farmer = filters.get('farmer') , vlcc = filters.get('vlcc'),txt= "%%%s%%" % text,as_list=True))

def req_cycle_computation(data):
	
	if data.get('emi_deduction_start_cycle') > 0:

		not_req_cycl = frappe.db.sql("""
				select name
			from
				`tabFarmer Date Computation`
			where
				'{0}' < start_date  or date('{0}') between start_date and end_date
				and vlcc = '{1}' order by start_date limit {2}""".format(data.get('date_of_disbursement'),data.get('vlcc'),data.get('emi_deduction_start_cycle')),as_dict=1,debug=0)

		not_req_cycl_list = [ '"%s"'%i.get('name') for i in not_req_cycl ]
		
		instalment = int(data.get('no_of_instalments')) + int(data.get('extension'))
		req_cycle = frappe.db.sql("""
					select name
				from
					`tabFarmer Date Computation`
				where
					'{date}' <= start_date and name not in ({cycle}) and vlcc = '{vlcc}' order by start_date limit {instalment}
				""".format(date=data.get('date_of_disbursement'), cycle = ','.join(not_req_cycl_list),vlcc = data.get('vlcc'),
					instalment = instalment),as_dict=1,debug=0)
		req_cycl_list = [i.get('name') for i in req_cycle]
		return req_cycl_list

	elif data.get('emi_deduction_start_cycle') == 0:
		instalment = int(data.get('no_of_instalments')) + int(data.get('extension'))
		req_cycle = frappe.db.sql("""
					select
						name
					from
						`tabFarmer Date Computation`
					where
					'{date}' <= end_date and vlcc = '{vlcc}'
						order by start_date limit {instalment}
				""".format(date=data.get('date_of_disbursement'),vlcc=data.get('vlcc'),instalment = instalment),as_dict=1,debug=0)
		req_cycl_list = [i.get('name') for i in req_cycle]
		return req_cycl_list
	return []

def get_conditions(data):
	conditions = " and 1=1"
	if data.get('emi_deduction_start_cycle'):
		conditions += ' limit {0}'.format(data.get('emi_deduction_start_cycle'))
	return conditions

def get_cycle_cond(data,not_req_cycl_list):
	conditions = " and 1=1"
	if data.get('emi_deduction_start_cycle'):
		conditions += ' and name not in ({cycle})'.format(cycle = ','.join(not_req_cycl_list))
	else:
		conditions += ' and name in ({cycle})'.format(cycle = ','.join(not_req_cycl_list))
	return conditions

def get_current_cycle(data):
	return frappe.db.sql("""
			select name 
		from
			`tabFarmer Date Computation`
		where
			vlcc = %s and now() between start_date and end_date
		""",(data.get('vlcc')),as_dict=1)

def req_cycle_computation_advance(data):
	
	if data.get('emi_deduction_start_cycle') > 0:

		not_req_cycl = frappe.db.sql("""
				select name
			from
				`tabFarmer Date Computation`
			where
				'{0}' < start_date  or date('{0}') between start_date and end_date
				and vlcc = '{1}' order by start_date limit {2}""".format(data.get('date_of_disbursement'),data.get('vlcc'),data.get('emi_deduction_start_cycle')),as_dict=1,debug=0)
		
		not_req_cycl_list = [ '"%s"'%i.get('name') for i in not_req_cycl ]
		
		instalment = int(data.get('no_of_instalment')) + int(data.get('extension'))
		req_cycle = frappe.db.sql("""
					select name
				from
					`tabFarmer Date Computation`
				where
					'{date}' <= start_date and name not in ({cycle}) and vlcc = '{vlcc}' order by start_date limit {instalment}
				""".format(date=data.get('date_of_disbursement'), cycle = ','.join(not_req_cycl_list),vlcc = data.get('vlcc'),
					instalment = instalment),as_dict=1,debug=0)
		req_cycl_list = [i.get('name') for i in req_cycle]
		return req_cycl_list

	elif data.get('emi_deduction_start_cycle') == 0:
		instalment = int(data.get('no_of_instalment')) + int(data.get('extension'))
		req_cycle = frappe.db.sql("""
					select
						name
					from
						`tabFarmer Date Computation`
					where
					'{date}' <= end_date and vlcc= '{vlcc}'
						order by start_date limit {instalment}
				""".format(date=data.get('date_of_disbursement'),vlcc=data.get('vlcc'),instalment = instalment),as_dict=1,debug=0)
		req_cycl_list = [i.get('name') for i in req_cycle]
		return req_cycl_list
	
	return []


def get_loans_child(start_date, end_date, vlcc, farmer_id, cycle=None):
	loans_ = frappe.db.sql("""
				select name,farmer_id,outstanding_amount,
				emi_amount,no_of_instalments,paid_instalment,advance_amount,
				emi_deduction_start_cycle,extension,date_of_disbursement,vlcc
			from 
				`tabFarmer Loan`
			where
				farmer_id = '{0}' and outstanding_amount != 0 and date_of_disbursement < now()	and docstatus =1
				""".format(farmer_id),as_dict=1,debug=0)
	loans = []
	for row in loans_:
		req_cycle = req_cycle_computation(row)
		if cycle in req_cycle_computation(row):
			loans.append(row)
	return loans


def get_advance_child(start_date, end_date, vlcc, farmer_id, cycle=None):
	advance_ = frappe.db.sql("""
				select name,farmer_id,outstanding_amount,emi_amount,advance_amount,
				no_of_instalment,paid_instalment,emi_deduction_start_cycle,
				extension,date_of_disbursement,vlcc
			from 
				`tabFarmer Advance`
			where
				farmer_id = '{0}' and outstanding_amount != 0 and date_of_disbursement < now() and docstatus =1	
			""".format(farmer_id),as_dict=1)
	advance = []
	for row in advance_:
		if cycle in req_cycle_computation_advance(row):
			advance.append(row)
	return advance


@frappe.whitelist()
def update_full_loan(loan=None):
	loan_doc = frappe.get_doc("Farmer Loan", loan)
	paid_amnt = float(loan_doc.advance_amount) - float(loan_doc.outstanding_amount)
	instlment = int(loan_doc.no_of_instalments) + int(loan_doc.extension) 
	instlment_brkup = float(loan_doc.interest) / instlment
	principle_paid = float(paid_amnt) - float(instlment_brkup) 




def fpcr_permission(user):
	roles = frappe.get_roles(user)
	user_doc = frappe.db.get_value("User",{"name":frappe.session.user},['operator_type','company','branch_office'], as_dict =1)

	if user != 'Administrator' and "Vlcc Manager" in roles:
		return """(`tabFarmer Payment Cycle Report`.vlcc_name = '{0}')""".format(user_doc.get('company'))

@frappe.whitelist()
def get_fpcr_flag():
	return frappe.db.get_value("Farmer Settings", {'vlcc':get_vlcc()}, 'is_fpcr')

def get_vlcc():
	return frappe.db.get_value("User",frappe.session.user, 'company')

# SG-6-10
@frappe.whitelist()
def get_updated_advance(cycle, data, adv_id, amount, total):
	data, total_paid, total_amount, overriding_amount = json.loads(data), 0, 0, 0
	for row in data.get('advance_child'):
		sum_ = frappe.db.sql("""
				select ifnull(sum(total_debit),0) as total
			from 
				`tabJournal Entry` 
			where 
			farmer_advance =%s  and cycle =%s and type='Farmer Advance' """,(row.get('adv_id'),cycle),as_dict=1,debug=0)
		total_paid += sum_[0].get('total')
		total_amount += row.get('principle')
		overriding_amount += flt(row.get('amount'))
	return flt((total_amount - overriding_amount),2) or 0


@frappe.whitelist()
def get_updated_loan(cycle, data, loan_id=None, amount=None, total = None):
	data, total_paid, total_amount, overriding_amount = json.loads(data), 0, 0, 0
	for row in data.get('loan_child'):
		total_amount += row.get('principle')
		overriding_amount += row.get('amount')
	return flt((total_amount - overriding_amount),2) or 0