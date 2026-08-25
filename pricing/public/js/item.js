
frappe.ui.form.on('Item', {
    refresh: function (frm) {
        console.log("Pricing Item JS Loaded", frm.doc.item_code, frm.doc.custom_url);
        if (!frm.is_new() && frm.doc.custom_url) {
            frm.add_custom_button(__('Update Supplier Price'), function () {
                frappe.call({
                    method: 'pricing.scripts.fabric_scraper.update_single_item',
                    args: {
                        item_code: frm.doc.item_code
                    },
                    freeze: true,
                    freeze_message: __('Updating Price from Supplier...'),
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Price updated successfully'));
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Actions'));
        }
    }
});
