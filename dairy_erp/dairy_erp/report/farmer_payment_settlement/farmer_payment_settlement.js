// Copyright (c) 2016, indictrans technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Farmer Payment Settlement"] = {

	"filters": [
		{
			"fieldname":"cycle",
			"label": __("Cycle"),
			"fieldtype": "Link",
			"options": "Farmer Date Computation",
			"on_change":function(query_report){
				frappe.call({	
					method:"dairy_erp.dairy_erp.report.farmer_payment_settlement.farmer_payment_settlement.get_dates",
					args:{
							"filters":query_report.get_values()
						},
				callback:function(r){
						if(r.message){
							frappe.query_report_filters_by_name.start_date.set_input(r.message[0].start_date);
							frappe.query_report_filters_by_name.end_date.set_input(r.message[0].end_date);
							query_report.trigger_refresh();		
						}
						else{
							frappe.query_report_filters_by_name.start_date.set_input(frappe.datetime.get_today());
							frappe.query_report_filters_by_name.end_date.set_input(frappe.datetime.get_today());
							query_report.trigger_refresh();
						}		
					}
				})
			},
			"get_query":function(){
				return{
					query:"dairy_erp.dairy_erp.report.farmer_payment_settlement.farmer_payment_settlement.get_settlement_per"	
				}

			}
		},
		{
			"fieldname":"farmer",
			"label": __("Farmer"),
			"fieldtype": "Link",
			"options":"Farmer",
			"reqd":1
		},
		{
			"fieldname":"start_date",
			"label": __("Start Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"read_only":1
		},
		{
			"fieldname":"end_date",
			"label": __("End Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"read_only":1
		},
		/*{
			"fieldname":"prev_transactions",
			"label": __("Previous Transactions"),
			"fieldtype": "Check"
		},*/

	],
	formatter: function(row, cell, value, columnDef, dataContext,default_formatter) {
			if (columnDef.df.label=="") {
				return repl("<input type='checkbox' \
					data-row='%(row)s' %(checked)s>", {
						row: row,
						checked: (dataContext.selected ? "checked=\"checked\"" : "")
					});
			}
			value = default_formatter(row, cell, value, columnDef, dataContext);
			return value
	},
	onload: function(report) {

		frappe.query_reports['Farmer Payment Settlement'].report_operation(report)
		frappe.query_reports['Farmer Payment Settlement'].get_default_cycle(report)

	},
	report_operation: function(report){
		var me = frappe.container.page.query_report;
		
		frappe.selected_rows = []

		report.page.add_inner_button(__("Payment Settlement"), function() {

			frappe.selected_rows = []

			$.each(me.data,function(i,d){
				if (d.selected == true){
					frappe.selected_rows.push(d.Name)
				}
			})

			if (frappe.selected_rows.length === 0){
				frappe.throw("Please select records")
			}
			frappe.query_reports['Farmer Payment Settlement'].get_summary_dialog(report)
		});

		$('body').on("click", "input[type='checkbox'][data-row]", function() {
			me.data[$(this).attr('data-row')].selected
					= this.checked ? true : false;
		})

	},
	get_summary_dialog:function(report){
		var dialog = new frappe.ui.Dialog({
		title: __("Payment Settlement"),
		fields: [
			{
				"label": __("Payble Amount"),
				"fieldname": "payble",
				"fieldtype": "Currency",
				"read_only": 1,
			},
			{
				"label": __("Receivable Amount"),
				"fieldname": "receivable",
				"fieldtype": "Currency",
				"read_only": 1,
			},
			{
				"label": __("Settlement Amount(Auto)"),
				"fieldname": "set_amt",
				"fieldtype": "Currency",
				"read_only": 1,
			},
			{
				"label": __("Settlement Amount(Manual)"),
				"fieldname": "set_amt_manual",
				"fieldtype": "Currency"
			},
			{
				"label": __("Mode Of Payment"),
				"fieldname": "mode_of_payment",
				"fieldtype": "Link",
				"options":"Mode of Payment"
			},
			{fieldtype: "Section Break",fieldname:"sec_brk"},
			{
				"label": __("Cheque/Reference No"),
				"fieldname": "ref_no",
				"fieldtype": "Data"
			},
			{fieldtype: "Column Break"},
			{
				"label": __("Cheque/Reference Date"),
				"fieldname": "ref_date",
				"fieldtype": "Date",
				"default": frappe.datetime.get_today(),
			}
		]
	});

	frappe.call({
		method:"dairy_erp.dairy_erp.report.farmer_payment_settlement.farmer_payment_settlement.get_payment_amt",
		args : {"row_data":frappe.selected_rows,"filters":report.get_values()},
		callback : function(r){
			dialog.set_values({
				'payble': r.message.payble,
				'receivable': r.message.receivable,
				"set_amt":r.message.set_amt,
				"set_amt_manual": r.message.payble - r.message.set_amt
			});
			if(r.message.payble <= r.message.receivable){
				dialog.get_field('set_amt_manual').df.hidden = 1;
				dialog.get_field('set_amt_manual').refresh();
				dialog.get_field('mode_of_payment').df.hidden = 1;
				dialog.get_field('mode_of_payment').refresh();
				dialog.get_field('ref_no').df.hidden = 1;
				dialog.get_field('ref_no').refresh();
				dialog.get_field('ref_date').df.hidden = 1;
				dialog.get_field('ref_date').refresh();
				dialog.get_field('sec_brk').df.hidden = 1;
				dialog.get_field('sec_brk').refresh();
			}
		}
	})
	
	dialog.show()

		dialog.set_primary_action(__("Submit"), function() {

			frappe.call({
				method:"dairy_erp.dairy_erp.report.farmer_payment_settlement.farmer_payment_settlement.make_payment",
				args : {
						"data":dialog.get_values(),
						"row_data":frappe.selected_rows,
						"filters":report.get_values()
						},
				callback : function(r){
					
					dialog.hide()
				}
			})
		})
	},
	get_default_cycle:function(report){
		frappe.call({
				method:"dairy_erp.dairy_erp.report.farmer_payment_settlement.farmer_payment_settlement.get_default_cycle",
				callback : function(r){
					if(r.message){
						frappe.query_report_filters_by_name.cycle.set_input(r.message[0].name);
						frappe.query_report_filters_by_name.start_date.set_input(r.message[0].start_date);
						frappe.query_report_filters_by_name.end_date.set_input(r.message[0].end_date);
						report.trigger_refresh();		
					}
					else{
						frappe.query_report_filters_by_name.start_date.set_input(frappe.datetime.get_today());
						frappe.query_report_filters_by_name.end_date.set_input(frappe.datetime.get_today());
						report.trigger_refresh();
					}
				}
			})
	}

}
