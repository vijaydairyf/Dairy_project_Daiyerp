// Copyright (c) 2018, Stellapps Technologies Private Ltd.
// For license information, please see license.txt

frappe.ui.form.on('Material Price List', {
	refresh: function(frm) {

		var template = ['GTVLCCB','GTFS','GTCS','GTCOVLCCB','GTCOB','GTCOS','LCOVLCCB'+"-"+frm.doc.camp_office]

		if (!in_list(frappe.user_roles,"Dairy Manager") && !frm.doc.__islocal){
			if (in_list(template,frm.doc.price_list)){
				frm.set_df_property("price_template_type", "read_only",1);
				frm.set_df_property("operator_name", "read_only",1);
				frm.set_df_property("items", "read_only",1);
				frm.set_df_property("price_list_template", "hidden",1);
				var price = frappe.meta.get_docfield('Material Price', "price", frm.doc.name);
				var item = frappe.meta.get_docfield('Material Price', "item", frm.doc.name);
				var item_name = frappe.meta.get_docfield('Material Price', "item_name", frm.doc.name);
				price.read_only = 1;
				item_name.read_only = 1;
				item.read_only = 1;
			}
		}
		else if(!frm.doc.__islocal && has_common(frappe.user_roles, ["Dairy Operator", "Dairy Manager"])){
			if (frm.doc.price_list == 'GTCOVLCCB'){
				frm.set_df_property("price_template_type", "read_only",1);
				frm.set_df_property("operator_name", "read_only",1);
				frm.set_df_property("items", "read_only",1);
				frm.set_df_property("price_list_template", "hidden",1);	
				var price = frappe.meta.get_docfield('Material Price', "price", frm.doc.name);
				var item = frappe.meta.get_docfield('Material Price', "item", frm.doc.name);
				var item_name = frappe.meta.get_docfield('Material Price', "item_name", frm.doc.name);
				price.read_only = 1;
				item_name.read_only = 1;
				item.read_only = 1;
			}
		}

		if(frm.doc.__islocal && has_common(frappe.user_roles, ["Dairy Operator", "Dairy Manager"])){
			frm.set_df_property("price_list_template", "hidden",1);	
		}
		if(has_common(frappe.user_roles, ["Camp Operator", "Camp Manager"])) {
			frm.set_df_property("price_template_type", "options", [' ','Dairy Supplier','CO to VLCC']);
		}
		else if(has_common(frappe.user_roles, ["Vlcc Operator", "Vlcc Manager"])) {
			frm.set_df_property("price_template_type", "options", [' ','VLCC Local Supplier','VLCC Local Farmer','VLCC Local Customer']);
		}

	},
	price_template_type: function(frm) {
		if(cur_frm.doc.price_template_type == "CO to VLCC"){
			frm.set_value("selling",1)
			frm.set_value("buying",0)
		}
		else if(cur_frm.doc.price_template_type == "Dairy Supplier"){
			frm.set_value("buying",1)
			frm.set_value("selling",0)
		}
		else if(cur_frm.doc.price_template_type == "VLCC Local Supplier"){
			frm.set_value("buying",1)
			frm.set_value("selling",0)
		}
		else if(cur_frm.doc.price_template_type == "VLCC Local Farmer"){
			frm.set_value("buying",0)
			frm.set_value("selling",1)
		}
		else if(cur_frm.doc.price_template_type == "VLCC Local Customer"){
			frm.set_value("buying",0)
			frm.set_value("selling",1)
		}
	},
	price_list_template: function(frm){
		if (frm.doc.price_list_template) {
			frappe.call({
				method: "dairy_erp.dairy_erp.doctype.material_price_list.material_price_list.get_template",
				args: {
					"template": frm.doc.price_list_template
				},
				callback: function(r) {
					frm.set_value("items" ,"");
					if (r.message) {
						$.each(r.message.items, function(i, d) {
							var row = frappe.model.add_child(cur_frm.doc, "Material Price", "items");
							row.item = d.item;
							row.item_name = d.item_name;
							row.price = d.price;
						});
					}
					refresh_field("items");
				}
			});
		};
		// frm.set_value("items" ,"");

	},
	onload: function(frm){
		if(has_common(frappe.user_roles, ["Camp Operator", "Camp Manager"])) {
			frm.set_query("price_list_template", function () {
				if(frm.doc.price_template_type == 'Dairy Supplier'){
					
					return {
						"filters": {
							"price_list": ["=","GTCOB"]
						}
					};
				}
				else if(frm.doc.price_template_type == 'CO to VLCC'){
					return {
						"filters": {
							"price_list": ["=","GTCOS"]
						}
					};
				}
				else{
					return {
						"filters": {
							"price_list": ["=",""]
						}
					}
				}
			});
		}
		else if (has_common(frappe.user_roles, ["Vlcc Operator", "Vlcc Manager"])) {
			frm.set_query("price_list_template", function () {
				if(frm.doc.price_template_type == 'VLCC Local Supplier'){			
					return {
						"filters": {
							"price_list": ["=","GTVLCCB"]
						}
					};
				}
				else if(frm.doc.price_template_type == 'VLCC Local Farmer'){
					return {
						"filters": {
							"price_list": ["=","GTFS"]
						}
					};
				}
				else if(frm.doc.price_template_type == 'VLCC Local Customer'){
					return {
						"filters": {
							"price_list": ["=","GTCS"]
						}
					};
				}
				else{
					return {
						"filters": {
							"price_list": ["=",""]
						}
					}
				}
			});
		}
	}
});


cur_frm.fields_dict['items'].grid.get_field("item").get_query = function(doc, cdt, cdn) {

	var item_list = []
	for(var i = 0 ; i < cur_frm.doc.items.length ; i++){
		if(cur_frm.doc.items[i].item){
			item_list.push(cur_frm.doc.items[i].item);
		}
	}
	return {
	filters: [
			['Item', 'name', 'not in', item_list]
		]
	}
}

