// Copyright (c) 2018, Stellapps Technologies Private Ltd.
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["VLCC Payment Settlement"] = {

	"filters": [
			{
				"fieldname":"select_all",
				"label": __("Select All"),
				"fieldtype": "Check",
				"default":1
			},
			{
				"fieldname":"vlcc",
				"label": __("VLCC"),
				"fieldtype": "Link",
				"options":"Village Level Collection Centre",
				"reqd":1
			},
			{
				"fieldname":"cycle",
				"label": __("Cycle"),
				"fieldtype": "Link",
				"options": "Cyclewise Date Computation",
				"reqd":1,
				"on_change":function(query_report){

					var me = frappe.container.page.query_report;
					frappe.call({	
						method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.get_dates",
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
			"get_query":function(query_report){
				var vlcc = frappe.query_report_filters_by_name.vlcc.get_value()
				return{
					query:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.get_settlement_per",
					filters: {
						"vlcc": vlcc
					}
				}
			}
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
		{
			"fieldname":"prev_transactions",
			"label": __("Previous Transactions"),
			"fieldtype": "Check"
		}
	],
	formatter: function(row, cell, value, columnDef, dataContext,default_formatter) {
		var me = frappe.container.page.query_report;
		var select_all = frappe.query_report_filters_by_name.select_all.get_value()
			if (columnDef.df.label=="") {
				me.data[row].selected
					= select_all ? true : false;

				return repl("<input type='checkbox' \
					data-row='%(row)s' %(checked)s>", {
						row: row,
						checked: select_all?"checked=\"checked\"":""
					});

			}
			value = default_formatter(row, cell, value, columnDef, dataContext);
			return value
	},
	onload: function(report) {

		frappe.query_reports['VLCC Payment Settlement'].report_operation(report)

	},
	report_operation: function(report){
		var me = frappe.container.page.query_report;
		var filters = report.get_values()
		var flag = true;
		frappe.selected_rows = []

		report.page.add_inner_button(__("Payment Settlement"), function() {
			filters = report.get_values()
			frappe.call({
				method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.is_vpcr_generated",
				args : {
						"filters":filters						},
				async: false,
				callback : function(r){
					if(r.message == 'creat'){
						flag = false
						frappe.throw(__("Please Generate <b>VPCR</b> for the cycle <b>{0}</b> against vlcc <b>{1}</b>",
							[frappe.query_report_filters_by_name.cycle.get_value(),frappe.query_report_filters_by_name.vlcc.get_value()]))
					}
				}
			})
			if(flag){
				frappe.selected_rows = []

				$.each(me.data,function(i,d){
					if (d.selected == true){
						frappe.selected_rows.push(d.Name)
					}
				})

				if (frappe.selected_rows.length === 0){
					frappe.throw("Please select records")
				}

				var end_date = frappe.query_report_filters_by_name.end_date.get_value()
				if(frappe.datetime.str_to_obj(frappe.datetime.get_today()) < frappe.datetime.str_to_obj(end_date)){
					frappe.throw(__("Settlement can be done after <b>{0}</b>",[frappe.datetime.str_to_user(end_date)]))
				}
				frappe.query_reports['VLCC Payment Settlement'].check_cycle(report)
			}
		});

		report.page.add_inner_button(__("Skip Cycle"), function() {

			frappe.call({
				method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.skip_cycle",
				args : {
						"row_data":frappe.selected_rows,
						"filters":report.get_values()
						},
				callback : function(r){			
				}
			})
		});
		report.page.add_inner_button(__("Generate Incentive"), function() {

			frappe.call({
				method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.generate_incentive",
				args : {
						"filters":report.get_values()
						},
				callback : function(r){			
				}
			})
		});

		$('body').on("click", "input[type='checkbox'][data-row]", function() {
			me.data[$(this).attr('data-row')].selected
					= this.checked ? true : false;
		})

	},
	check_cycle: function(report){
		frappe.call({
				method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.check_cycle",
				args : {
						"row_data":frappe.selected_rows,
						"filters":report.get_values()
						},
				callback : function(r){	
					if(r.message.recv_msg){
						frappe.throw(r.message.recv_msg)
					}else if (r.message.cycle_msg){
						frappe.throw(r.message.cycle_msg)
					}
					else{
						frappe.query_reports['VLCC Payment Settlement'].get_summary_dialog(report)
					}		
				}
			})
	},
	get_summary_dialog:function(report){
		var dialog = new frappe.ui.Dialog({
		title: __("Payment Settlement"),
		fields: [
			{
				"label": __("Payable Amount"),
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
				"fieldtype": "Data",
				"reqd":1
			},
			{fieldtype: "Column Break"},
			{
				"label": __("Cheque/Reference Date"),
				"fieldname": "ref_date",
				"fieldtype": "Date",
				"default": frappe.datetime.get_today(),
				"reqd":1
			}
		]
	});

	frappe.call({
		method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.get_payment_amt",
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
				dialog.get_field('ref_no').df.reqd = 0;
				dialog.get_field('ref_no').refresh();
				dialog.get_field('ref_date').df.reqd = 0;
				dialog.get_field('ref_date').refresh();
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

		frappe.query_reports['VLCC Payment Settlement'].validate_amount(dialog)

		frappe.call({
			method:"dairy_erp.dairy_erp.report.vlcc_payment_settlement.vlcc_payment_settlement.make_payment",
			args : {
					"data":dialog.get_values(),
					"row_data":frappe.selected_rows,
					"filters":report.get_values()
					},
			callback : function(r){
				if (r.message){
					var payable = r.message.payable
					var receivable = r.message.receivable
					var due_pay = r.message.due_pay
					if (payable && receivable && due_pay){	
						frappe.msgprint(__("Payment Entry {0}, {1}, {2} has been created",
							[repl('<a href="#Form/Payment Entry/%(payable)s" class="strong">%(payable)s</a>', {
								payable: payable
							}),
							repl('<a href="#Form/Payment Entry/%(receivable)s" class="strong">%(receivable)s</a>', {
								receivable: receivable
							}),
							repl('<a href="#Form/Payment Entry/%(due_pay)s" class="strong">%(due_pay)s</a>', {
								due_pay: due_pay
							})]
						));
					}
					else if(payable && receivable){
						frappe.msgprint(__("Payment Entry {0}, {1} has been created",
							[repl('<a href="#Form/Payment Entry/%(payable)s" class="strong">%(payable)s</a>', {
								payable: payable
							}),
							repl('<a href="#Form/Payment Entry/%(receivable)s" class="strong">%(receivable)s</a>', {
								receivable: receivable
							})]
						));

					}
					else if(due_pay){
						frappe.msgprint(__("Payment Entry {0} has been created",
							[repl('<a href="#Form/Payment Entry/%(due_pay)s" class="strong">%(due_pay)s</a>', {
								due_pay: due_pay
							})]
						));
					}
				}		
				dialog.hide()
			}
		})
		})
	},
	validate_amount:function(dialog){
		var data = dialog.get_values()
		if(data.set_amt && data.set_amt_manual && (data.set_amt_manual > (data.payble - data.set_amt))){		
				frappe.throw(__("<b>Settlement Amount {0}</b> cannot be greater than <b>Payable Amount {1}</b>",
					[data.set_amt_manual,data.payble-data.set_amt.toFixed(2)]))
		}
		else if(data.payble && !data.set_amt && (data.set_amt_manual > data.payble)){
			frappe.throw(__("<b>Settlement Amount {0}</b> cannot be greater than <b>Payable Amount {1}</b>",
				[data.set_amt_manual,data.payble]))
		}
		if(data.set_amt_manual < 0){
			frappe.throw(__("Payable Amount can not be negative"))
		}
		else if(data.set_amt_manual === 0){
			frappe.throw(__("Payable Amount can not be zero"))
		}
	}
}