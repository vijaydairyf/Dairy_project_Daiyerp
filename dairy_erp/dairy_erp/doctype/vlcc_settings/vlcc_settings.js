// Copyright (c) 2018, indictrans technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('VLCC Settings', {
	refresh: function(frm) {
		frm.events.set_vlcc(frm)
		// frm.set_df_property("farmer_id1", "read_only", frm.doc.__islocal ? 0:1);
		// frm.set_df_property("farmer_id2", "read_only", frm.doc.__islocal ? 0:1);
	},
	hours: function(frm) {
		if (frm.doc.hours > 48) {
			frappe.msgprint("Hours can not be more than 48")
			frm.set_value("hours",24)
			frm.reload_doc();
		}
		else if(frm.doc.hours < 0) {
			frappe.msgprint("Hours can not negative")
			frm.set_value("hours",24)
			frm.reload_doc();
		} else if(frm.doc.cycle_hours && frm.doc.hours > frm.doc.cycle_hours){
			frappe.msgprint("FMCR Edition Hours must be less than Farmer Payment Settlement Hours")
		}
	},
	cycle_hours: function(frm) {
		frm.events.validate_cycle_hours(frm)	
	},
	months_to_member: function(frm){
		if(frm.doc.months_to_member >999) {
			frappe.msgprint("Months can not be greater than 999")
			frm.set_value("months_to_member",0)
			frm.reload_doc();
		}
	},
	validate: function(frm) {
		frm.events.validate_cycle_hours(frm)
	},
	set_vlcc: function(frm){
		frappe.call({
				method: "frappe.client.get_value",
				async : false,
				args: {
					doctype: "User",
					filters: {"name": frappe.session.user},
					fieldname: ["company"]
				},
				callback: function(r){
					if(r.message){
						if(!frm.doc.vlcc){
							frm.set_value("vlcc",r.message.company)
						}
						frm.events.check_record_exist(frm)
					}
				}
			});
	},
	check_record_exist: function(frm){
		if(frm.doc.__islocal){	
			frappe.call({	
				method:"dairy_erp.dairy_erp.doctype.vlcc_settings.vlcc_settings.check_record_exist",	
				callback:function(r){
					if(r.message){
						frappe.msgprint("Please add configurations in the existing settings")
						frappe.set_route("List","VLCC Settings")
					}
				}
			})
		}
	},
	validate_cycle_hours: function(frm) {
		if(frm.doc.cycle_hours % 24 != 0){
			frappe.msgprint("Please add Hours in multiples of 24")
			frm.set_value("cycle_hours",24)
			frm.reload_doc();
		} else if(frm.doc.cycle_hours == 0){
			frappe.msgprint("Hours can not be zero")
			frm.set_value("cycle_hours",24)
			frm.reload_doc();
		} else if(frm.doc.hours && (frm.doc.cycle_hours < frm.doc.hours)){
			frappe.msgprint("Configurable Hours for Farmer Payment Settlement must be greater than FMCR Edition Hours")
			frm.set_value("cycle_hours",24)
			frm.reload_doc();
		}
	}
});


cur_frm.fields_dict['vlcc_item'].grid.get_field("item").get_query = function(doc, cdt, cdn) {
		var child = locals[cdt][cdn];
		return {
			query:"dairy_erp.dairy_erp.doctype.vlcc_settings.vlcc_settings.get_item_by_customer_type",
			filters: {'customer_type': child.customer_type,
						'items_dict':cur_frm.doc.vlcc_item
					}
		}
}
