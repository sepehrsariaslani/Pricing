frappe.ui.form.on('Raw Material Pricing', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Update Market Data'), function() {
                frm.call('update_market_data').then(r => {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint(r.message.message);
                        frm.refresh();
                    }
                });
            });
            
            frm.add_custom_button(__('Calculate Cost Impact'), function() {
                frm.call('calculate_cost_impact').then(() => {
                    frm.refresh();
                });
            });
            
            frm.add_custom_button(__('Price Analytics'), function() {
                show_price_analytics(frm);
            }, __('Reports'));
            
            frm.add_custom_button(__('Material Dashboard'), function() {
                show_material_dashboard();
            }, __('Reports'));
            
            frm.add_custom_button(__('Price History Chart'), function() {
                show_price_history_chart(frm);
            }, __('Charts'));
            
            frm.add_custom_button(__('Impact Analysis'), function() {
                show_impact_analysis(frm);
            }, __('Analysis'));
        }
        
        // Set default values
        if (frm.is_new()) {
            frm.set_value('effective_date', frappe.datetime.get_today());
            frm.set_value('status', 'Active');
            frm.set_value('price_alert_threshold', 5);
            frm.set_value('monitoring_frequency', 'Weekly');
        }
        
        // Highlight price changes
        if (frm.doc.price_change_percent) {
            let change = flt(frm.doc.price_change_percent);
            if (Math.abs(change) > 10) {
                frm.dashboard.add_indicator(__('Significant Price Change'), change > 0 ? 'red' : 'green');
            }
        }
        
        // Show cost impact summary
        if (frm.doc.total_cost_impact && frm.doc.total_cost_impact !== 0) {
            let impact = flt(frm.doc.total_cost_impact);
            frm.dashboard.add_indicator(
                __('Cost Impact: ') + frappe.format(Math.abs(impact), {fieldtype: 'Currency'}),
                impact > 0 ? 'red' : 'green'
            );
        }
    },
    
    material_code: function(frm) {
        if (frm.doc.material_code) {
            // Get material details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Item',
                    name: frm.doc.material_code
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('material_name', r.message.item_name);
                        frm.set_value('uom', r.message.stock_uom);
                        if (!frm.doc.material_category) {
                            frm.set_value('material_category', r.message.item_group);
                        }
                    }
                }
            });
            
            // Get current price from Item Price
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Price',
                    filters: {
                        item_code: frm.doc.material_code,
                        buying: 1
                    },
                    fieldname: 'price_list_rate'
                },
                callback: function(r) {
                    if (r.message && r.message.price_list_rate && !frm.doc.current_price) {
                        frm.set_value('current_price', r.message.price_list_rate);
                    }
                }
            });
        }
    },
    
    current_price: function(frm) {
        if (frm.doc.current_price && frm.doc.previous_price) {
            calculate_price_changes(frm);
        }
    },
    
    previous_price: function(frm) {
        if (frm.doc.current_price && frm.doc.previous_price) {
            calculate_price_changes(frm);
        }
    }
});

function calculate_price_changes(frm) {
    let current = flt(frm.doc.current_price);
    let previous = flt(frm.doc.previous_price);
    
    if (current && previous) {
        let change = current - previous;
        let change_percent = (change / previous) * 100;
        
        frm.set_value('price_change', change);
        frm.set_value('price_change_percent', change_percent);
    }
}

function show_price_analytics(frm) {
    frappe.call({
        method: 'get_price_analytics',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                show_analytics_dialog(r.message);
            }
        }
    });
}

function show_analytics_dialog(analytics) {
    let dialog = new frappe.ui.Dialog({
        title: __('Price Analytics'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'analytics_html'
            }
        ]
    });
    
    let html = generate_analytics_html(analytics);
    dialog.fields_dict.analytics_html.$wrapper.html(html);
    dialog.show();
}

function generate_analytics_html(data) {
    let html = `
        <div class="price-analytics">
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Current Status</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Current Price:</td><td>${frappe.format(data.current_status.current_price, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Market Price:</td><td>${frappe.format(data.current_status.market_price, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Price vs Market:</td><td>${data.current_status.price_vs_market.toFixed(2)}%</td></tr>
                                <tr><td>Trend:</td><td><span class="badge badge-${data.current_status.trend === 'Rising' ? 'danger' : data.current_status.trend === 'Falling' ? 'success' : 'info'}">${data.current_status.trend}</span></td></tr>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Cost Impact Summary</h6></div>
                        <div class="card-body">
                            <table class="table table-sm">
                                <tr><td>Affected Items:</td><td>${data.cost_impact_summary.total_affected_items || 0}</td></tr>
                                <tr><td>High Impact Items:</td><td>${data.cost_impact_summary.high_impact_items || 0}</td></tr>
                                <tr><td>Total Impact:</td><td>${frappe.format(data.cost_impact_summary.total_cost_impact, {fieldtype: 'Currency'})}</td></tr>
                                <tr><td>Avg Impact/Item:</td><td>${frappe.format(data.cost_impact_summary.avg_impact_per_item, {fieldtype: 'Currency'})}</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

function show_material_dashboard() {
    frappe.call({
        method: 'pricing.pricing.doctype.raw_material_pricing.raw_material_pricing.get_raw_material_dashboard',
        callback: function(r) {
            if (r.message) {
                show_dashboard_dialog(r.message);
            }
        }
    });
}

function show_dashboard_dialog(dashboard_data) {
    let dialog = new frappe.ui.Dialog({
        title: __('Raw Material Dashboard'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'dashboard_html'
            }
        ]
    });
    
    let html = generate_material_dashboard_html(dashboard_data);
    dialog.fields_dict.dashboard_html.$wrapper.html(html);
    dialog.show();
}

function generate_material_dashboard_html(data) {
    let html = `
        <div class="material-dashboard">
            <div class="row">
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">${data.active_materials}</h2>
                            <p>Active Materials</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-warning">${data.volatile_materials}</h2>
                            <p>Volatile Materials</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-danger">${data.attention_materials}</h2>
                            <p>Need Attention</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Recent Materials</h6></div>
                        <div class="card-body">
                            ${data.material_list.map(material => `
                                <div class="d-flex justify-content-between">
                                    <span>${material.material_name}</span>
                                    <span class="text-${material.price_change_percent > 0 ? 'danger' : 'success'}">
                                        ${material.price_change_percent ? material.price_change_percent.toFixed(1) + '%' : '0%'}
                                    </span>
                                </div>
                            `).join('<hr>')}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>High Attention Materials</h6></div>
                        <div class="card-body">
                            ${data.attention_list.length > 0 ? data.attention_list.map(material => `
                                <div class="d-flex justify-content-between">
                                    <span>${material.material_name}</span>
                                    <span class="badge badge-danger">${material.price_change_percent.toFixed(1)}%</span>
                                </div>
                            `).join('<hr>') : '<p>No materials need immediate attention</p>'}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

function show_price_history_chart(frm) {
    if (!frm.doc.price_history || frm.doc.price_history.length === 0) {
        frappe.msgprint(__('No price history available'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('Price History Chart'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'chart_html'
            }
        ]
    });
    
    let html = generate_price_history_chart_html(frm.doc.price_history);
    dialog.fields_dict.chart_html.$wrapper.html(html);
    dialog.show();
}

function generate_price_history_chart_html(price_history) {
    // Sort by date
    let sorted_history = price_history.sort((a, b) => new Date(a.date) - new Date(b.date));
    
    let html = `
        <div class="price-history-chart">
            <h4>Price History</h4>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Price</th>
                            <th>Change</th>
                            <th>Change %</th>
                            <th>Source</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    sorted_history.forEach(history => {
        let change_class = history.price_change > 0 ? 'text-danger' : history.price_change < 0 ? 'text-success' : 'text-muted';
        
        html += `
            <tr>
                <td>${frappe.datetime.str_to_user(history.date)}</td>
                <td>${frappe.format(history.price, {fieldtype: 'Currency'})}</td>
                <td class="${change_class}">
                    ${history.price_change ? frappe.format(history.price_change, {fieldtype: 'Currency'}) : '-'}
                </td>
                <td class="${change_class}">
                    ${history.price_change_percent ? history.price_change_percent.toFixed(2) + '%' : '-'}
                </td>
                <td>${history.source || '-'}</td>
            </tr>
        `;
    });
    
    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    return html;
}

function show_impact_analysis(frm) {
    if (!frm.doc.affected_items || frm.doc.affected_items.length === 0) {
        frappe.msgprint(__('No affected items found'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('Cost Impact Analysis'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'impact_html'
            }
        ]
    });
    
    let html = generate_impact_analysis_html(frm.doc.affected_items);
    dialog.fields_dict.impact_html.$wrapper.html(html);
    dialog.show();
}

function generate_impact_analysis_html(affected_items) {
    let html = `
        <div class="impact-analysis">
            <h4>Cost Impact Analysis</h4>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Current Cost</th>
                            <th>New Cost</th>
                            <th>Impact</th>
                            <th>Severity</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    affected_items.forEach(item => {
        let severity_class = item.impact_severity === 'Critical' ? 'danger' : 
                           item.impact_severity === 'High' ? 'warning' : 
                           item.impact_severity === 'Medium' ? 'info' : 'secondary';
        
        html += `
            <tr>
                <td><strong>${item.item_name || item.item_code}</strong></td>
                <td>${frappe.format(item.current_cost_per_unit, {fieldtype: 'Currency'})}</td>
                <td>${frappe.format(item.new_cost_per_unit, {fieldtype: 'Currency'})}</td>
                <td class="text-${item.total_cost_impact > 0 ? 'danger' : 'success'}">
                    ${frappe.format(item.total_cost_impact, {fieldtype: 'Currency'})}
                </td>
                <td><span class="badge badge-${severity_class}">${item.impact_severity}</span></td>
                <td>${item.recommended_action}</td>
            </tr>
        `;
    });
    
    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    return html;
}
