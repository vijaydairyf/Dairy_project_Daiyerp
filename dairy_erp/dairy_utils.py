# -*- coding: utf-8 -*-
# Copyright (c) 2018, Stellapps Technologies Private Ltd.
# For license information, please see license.txt
# Author Khushal Trivedi

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import requests
from frappe.utils import flt, now_datetime, cstr, random_string, nowdate
import json
from dairy_erp.report.farmer_net_payoff.farmer_net_payoff import get_data
from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport


def make_dairy_log(**kwargs):
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

def make_agrupay_log(**kwargs):
	ag_log = frappe.get_doc({"doctype": "AgRupay Log"})
	ag_log.update({
		"status": kwargs.get('status'),
		"request_data": kwargs.get('request_data'),
		"sync_time": kwargs.get('sync_time'),
		"response_text": kwargs.get('response_text'),
		"response_code": kwargs.get('response_code')
		})
	ag_log.insert(ignore_permissions=True)
	frappe.db.commit()
	return ag_log.name

def make_journal_entry(**kwargs):
	abbr = frappe.db.get_value("Company", kwargs.get('company'), ['abbr','cost_center'],as_dict=1)
	je_doc = frappe.new_doc("Journal Entry")
	je_doc.voucher_type = kwargs.get('voucher_type')
	je_doc.company = kwargs.get('company')
	je_doc.type = kwargs.get('type')
	je_doc.is_feed_and_fodder = kwargs.get('faf_flag')
	je_doc.cycle = kwargs.get('cycle')
	je_doc.farmer_advance = kwargs.get('master_no')
	je_doc.posting_date = kwargs.get('posting_date')
	je_doc.reference_party = kwargs.get('party')
	if kwargs.get("advance_type") == "Money Advance" or kwargs.get('type') == "Farmer Advance":
		je_doc.append('accounts', {
			'account': kwargs.get('debit_account')+ abbr.get('abbr'),
			'debit_in_account_currency': kwargs.get('amount'),
			'party_type': kwargs.get('party_type'),
			'party': kwargs.get('party'),
			'cost_center': abbr.get('cost_center')
			})
		je_doc.append('accounts', {
			'account': kwargs.get('credit_account')+ abbr.get('abbr'),
			'credit_in_account_currency': kwargs.get('amount'),
			'cost_center': abbr.get('cost_center')
			})
	elif kwargs.get("advance_type") == "Feed And Fodder Advance":
		je_doc.append('accounts', {
			'account': kwargs.get('debit_account')+ abbr.get('abbr'),
			'debit_in_account_currency': kwargs.get('amount'),
			'cost_center': abbr.get('cost_center')
			})
		je_doc.append('accounts', {
			'account': kwargs.get('credit_account')+ abbr.get('abbr'),
			'party_type': kwargs.get('party_type'),
			'party': kwargs.get('party'),
			'credit_in_account_currency': kwargs.get('amount'),
			'cost_center': abbr.get('cost_center')
			})
	elif kwargs.get('type') == "Debit to Loan":
		je_doc.append('accounts', {
			'account': kwargs.get('debit_account')+ abbr.get('abbr'),
			'debit_in_account_currency': kwargs.get('amount'),
			'party': kwargs.get('party'),
			'party_type': kwargs.get('party_type'),
			'cost_center': abbr.get('cost_center')
			})
		je_doc.append('accounts', {
			'account': kwargs.get('credit_account')+ abbr.get('abbr'),
			'credit_in_account_currency': kwargs.get('amount'),
			'cost_center': abbr.get('cost_center')
			})
	elif kwargs.get('type') == "Farmer Loan":
		je_doc.append('accounts', {
			'account': kwargs.get('debit_account')+ abbr.get('abbr'),
			'debit_in_account_currency': flt(kwargs.get('amount') + kwargs.get('interest_amount'),2),
			'party_type': kwargs.get('party_type'),
			'party': kwargs.get('party'),
			'cost_center': abbr.get('cost_center')
			})
		je_doc.append('accounts', {
			'account': kwargs.get('credit_account')+ abbr.get('abbr'),
			'credit_in_account_currency': kwargs.get('amount'),
			'cost_center': abbr.get('cost_center')
			})
		je_doc.append("accounts" , {
			'account': kwargs.get('interest_account')+ abbr.get('abbr'),
			'credit_in_account_currency': kwargs.get('interest_amount'),
			'cost_center': abbr.get('cost_center')
			})
	je_doc.flags.ignore_permissions =True	
	je_doc.save()
	je_doc.submit()
	return je_doc

