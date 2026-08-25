# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RawMaterialNotificationUser(Document):
    def validate(self):
        """Validate notification user data"""
        # Validate user exists
        if self.user:
            if not frappe.db.exists("User", self.user):
                frappe.throw(f"User {self.user} does not exist")
        
        # Validate threshold percentage
        if self.threshold_percent:
            if self.threshold_percent < 0 or self.threshold_percent > 100:
                frappe.throw("Threshold percentage must be between 0 and 100")
        
        # Set default notification type if not provided
        if not self.notification_type:
            self.notification_type = "Price Change"
        
        # Set default priority if not provided
        if not self.priority:
            self.priority = "Medium"
    
    def should_notify(self, price_change_percent, notification_type="Price Change"):
        """Check if user should be notified based on their preferences"""
        # Check if notification type matches
        if self.notification_type != "All" and self.notification_type != notification_type:
            return False
        
        # Check threshold
        if self.threshold_percent:
            return abs(flt(price_change_percent)) >= flt(self.threshold_percent)
        
        return True
    
    def get_user_details(self):
        """Get user details"""
        if self.user:
            return frappe.get_doc("User", self.user)
        return None
    
    def get_notification_preferences(self):
        """Get user's notification preferences"""
        return {
            'email_enabled': self.email_enabled,
            'sms_enabled': self.sms_enabled,
            'threshold_percent': self.threshold_percent,
            'priority': self.priority,
            'notification_type': self.notification_type
        }
    
    def send_notification(self, subject, message, notification_type="Price Change"):
        """Send notification to user based on their preferences"""
        if not self.should_notify(0, notification_type):  # Basic type check
            return False
        
        notifications_sent = []
        
        # Send email if enabled
        if self.email_enabled:
            try:
                frappe.sendmail(
                    recipients=[self.user],
                    subject=subject,
                    message=message,
                    priority=self.priority
                )
                notifications_sent.append("Email")
            except Exception as e:
                frappe.log_error(f"Failed to send email to {self.user}: {str(e)}")
        
        # Create system notification
        try:
            frappe.get_doc({
                'doctype': 'Notification Log',
                'subject': subject,
                'for_user': self.user,
                'type': 'Alert',
                'document_type': 'Raw Material Pricing',
                'email_content': message
            }).insert(ignore_permissions=True)
            notifications_sent.append("System")
        except Exception as e:
            frappe.log_error(f"Failed to create notification log for {self.user}: {str(e)}")
        
        return notifications_sent
