
frappe.ui.form.on('Selling Settings', {
    refresh: function (frm) {
        frm.add_custom_button(__('Update All Fabric Prices'), function () {
            frappe.confirm(__('Are you sure you want to update prices for all fabric items? This may take a while.'), function () {
                frappe.call({
                    method: 'pricing.scripts.fabric_scraper.trigger_update_all',
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(r.message);
                        }
                    }
                });
            });
        });
    }
});
