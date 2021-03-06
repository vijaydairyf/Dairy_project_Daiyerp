// Copyright (c) 2018, Stellapps Technologies Private Ltd.
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Vlcc Net Pay Off"] = {
	"filters": [
		{
			"fieldname":"camp",
			"label": __("Camp Operator"),
			"fieldtype": "Data",
			"default": frappe.session.user_fullname,
			"read_only": 1
			/*"get_query": function (query_report) {
				return {
					query:"dairy_erp.dairy_erp.report.farmer_net_payoff.farmer_net_payoff.get_filtered_camp_operator"
					
				}
			}*/
		},
		{
			"fieldname":"vlcc",
			"label": __("Vlcc"),
			"fieldtype": "Link",
			"options": "Village Level Collection Centre"
			/*"get_query": function (query_report) {
				return {
					query:"dairy_erp.dairy_erp.report.vlcc_net_pay_off.vlcc_net_pay_off.get_filtered_vlccs"
					
				}
			}*/
		},
		{
			"fieldname":"report_date",
			"label": __("As on Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname":"ageing_based_on",
			"label": __("Ageing Based On"),
			"fieldtype": "Select",
			"options": 'Posting Date\nDue Date',
			"default": "Posting Date"
		},
		{
			"fieldname":"account",
			"label": __("Account"),
			"fieldtype": "Link",
			"options": "Account"
		},
	]
}

