frappe.provide('pricing.auto_price_list');

frappe.ui.form.on('Auto Price List', {
    refresh: function(frm) {

        // Add custom button to update prices
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Update Prices'), function() {
                frappe.call({
                    method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.update_prices',
                    args: {
                        doctype: frm.doctype,
                        docname: frm.docname
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: r.message.message,
                                indicator: r.message.indicator
                            });
                        }
                    }
                });
            });
        }
    },
    
    profit_margin: function(frm) {
        calculate_prices(frm);
    },
    
    items_add: function(frm) {
        calculate_prices(frm);
    },
    
    items_remove: function(frm) {
        calculate_prices(frm);
    }
});

function calculate_prices(frm) {
    frappe.show_alert({
        message: __('Calculating prices...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'update_item_prices_with_details',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.show_alert({
                    message: r.message.message,
                    indicator: r.message.indicator
                });
            }
        },
        error: function(r) {
            frappe.show_alert({
                message: __('Error occurred. Please try again.'),
                indicator: 'red'
            });
        }
    });
} 