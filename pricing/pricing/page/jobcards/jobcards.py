import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, get_datetime, flt
from datetime import datetime, timedelta

def _get_workstation_rate_info(workstation_type: str):
    """Return hour rates for a workstation type and net hourly rate.

    Looks up a Workstation with the given workstation_type and reads custom hour
    rate fields provided by the user:
    - hour_rate_electricity
    - hour_rate_consumable
    - hour_rate_rent
    - hour_rate_labour

    Returns dict with each component and net_hour_rate (sum of components).
    If nothing is found, all values are 0.
    """
    if not workstation_type:
        return {
            "hour_rate_electricity": 0,
            "hour_rate_consumable": 0,
            "hour_rate_rent": 0,
            "hour_rate_labour": 0,
            "net_hour_rate": 0,
        }

    ws = frappe.get_all(
        "Workstation",
        filters={"workstation_type": workstation_type},
        fields=[
            "name",
            "hour_rate_electricity",
            "hour_rate_consumable",
            "hour_rate_rent",
            "hour_rate_labour",
        ],
        limit=1,
    )

    if not ws:
        return {
            "hour_rate_electricity": 0,
            "hour_rate_consumable": 0,
            "hour_rate_rent": 0,
            "hour_rate_labour": 0,
            "net_hour_rate": 0,
        }

    rec = ws[0]
    e = flt(rec.get("hour_rate_electricity") or 0)
    c = flt(rec.get("hour_rate_consumable") or 0)
    r = flt(rec.get("hour_rate_rent") or 0)
    l = flt(rec.get("hour_rate_labour") or 0)
    net = e + c + r + l
    return {
        "workstation": rec.get("name"),
        "hour_rate_electricity": e,
        "hour_rate_consumable": c,
        "hour_rate_rent": r,
        "hour_rate_labour": l,
        "net_hour_rate": net,
    }

def _compute_job_card_pricing(jc: dict):
    """Compute pricing info per job card.

    Rules (as requested):
    - minutes per unit = time_required / for_quantity
    - net hourly rate = sum of workstation hour rates
    - per unit price = (minutes_per_unit / 60) * (2/3 * net_hour_rate)
    - total price for the job card = per_unit_price * for_quantity
    Returns dict with computed fields and the rates.
    """
    qty = flt(jc.get("for_quantity") or 0)
    time_required = flt(jc.get("time_required") or 0)  # minutes (for full qty)
    ws_type = jc.get("workstation_type")

    rates = _get_workstation_rate_info(ws_type)
    net_hour_rate = flt(rates.get("net_hour_rate") or 0)

    minutes_per_unit = 0
    if qty > 0 and time_required > 0:
        minutes_per_unit = time_required / qty

    effective_hour_rate = (2.0 / 3.0) * net_hour_rate
    per_unit_price = (minutes_per_unit / 60.0) * effective_hour_rate
    total_price = per_unit_price * qty

    return {
        "minutes_per_unit": minutes_per_unit,
        "effective_hour_rate": effective_hour_rate,
        "per_unit_price": per_unit_price,
        "total_price": total_price,
        **rates,
    }

@frappe.whitelist()
def get_employee_job_cards(employee=None, date=None, status=None):
    """Get job cards for specific employee with filters"""
    
    if not employee:
        # Get current user's employee
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name", "workstation"]
        )
        if employee_doc:
            employee = employee_doc[0].name
            workstation = employee_doc[0].workstation
        else:
            frappe.throw(_("No employee found for current user"))
    else:
        employee_doc = frappe.get_doc("Employee", employee)
        workstation = employee_doc.workstation

    filters = {}
    
    # Workstation filter
    if workstation:
        filters["workstation_type"] = workstation
    
    # Date filter
    if date:
        filters["custom_planned_end_date"] = date
    
    # Status filter
    if status:
        if status == "available":
            filters["status"] = ["!=", "Completed"]
        else:
            filters["status"] = status
    else:
        # Default: exclude completed
        filters["status"] = ["!=", "Completed"]
    
    job_cards = frappe.get_all("Job Card",
        filters=filters,
        fields=[
            "name", "production_item", "operation", "status", "for_quantity",
            "work_order", "idx", "custom_job_card_priority", "custom_plan_employee",
            "custom_planned_start_date", "custom_planned_end_date", 
            "workstation_type", "creation", "modified", "sequence_id"
        ],
        order_by="custom_job_card_priority desc, sequence_id asc, idx asc, creation desc"
    )
    
    return job_cards

@frappe.whitelist()
def get_active_job_card(employee=None):
    """Get currently active job card for employee"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name", "workstation"]
        )
        if not employee_doc:
            return None
        employee = employee_doc[0].name
        workstation = employee_doc[0].workstation
    else:
        employee_doc = frappe.get_doc("Employee", employee)
        workstation = employee_doc.workstation
    
    if not workstation:
        return None
    
    active_job_cards = frappe.get_all("Job Card",
        filters={
            "workstation_type": workstation,
            "status": "Work In Progress"
        },
        fields=["name", "operation", "production_item", "work_order"],
        limit=1
    )
    
    if active_job_cards:
        return active_job_cards[0]
    
    return None



@frappe.whitelist()
def start_job_card(job_card_name, employee=None):
    """Start a job card and create time log entry"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name", "workstation"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
    
    # Check for active job by same employee
    active_employee_jobs = frappe.get_all("Job Card Time Log",
        filters={
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        fields=["parent", "name"],
        limit=1
    )

    if active_employee_jobs:
        current_job_name = active_employee_jobs[0].parent
        if current_job_name != job_card_name:
            # Return confirmation request instead of auto-pausing
            return {
                "status": "confirm_required", 
                "message": _("شما روی کارت کار دیگری کار می‌کنید"),
                "current_job": current_job_name,
                "current_job_operation": frappe.get_value("Job Card", current_job_name, "operation")
            }
        
    # Start the new job card
    frappe.db.set_value("Job Card", job_card_name, {
        "status": "Work In Progress",
        "actual_start_date": now_datetime()
    })
    
    # Create time log entry
    create_time_log_entry(job_card_name, employee, "start")
    
    frappe.db.commit()
    
    return {"status": "success", "message": _("Job Card started successfully")}


@frappe.whitelist()
def create_time_log_entry(job_card_name, employee, action_type):
    """Create or update time log entry for job card"""
    
    if action_type == "start":
        # Create new time log entry
        time_log = frappe.get_doc({
            "doctype": "Job Card Time Log",
            "parent": job_card_name,
            "parenttype": "Job Card",
            "parentfield": "time_logs",
            "employee": employee,
            "from_time": now_datetime(),
            "activity_type": "Manufacturing",
            "operation": frappe.get_value("Job Card", job_card_name, "operation")
        })
        
        time_log.insert()
        return time_log.name
    
    return None

@frappe.whitelist()
def update_time_log_entry(job_card_name, employee, action_type, completed_qty=None):
    """Update existing time log entry"""
    
    if action_type == "stop":
        # Find the latest open time log entry for this employee
        time_logs = frappe.get_all("Job Card Time Log",
            filters={
                "parent": job_card_name,
                "employee": employee,
                "to_time": ["is", "not set"]
            },
            fields=["name"],
            order_by="creation desc",
            limit=1
        )
        
        if time_logs:
            tl_name = time_logs[0].name
            from_time = frappe.db.get_value("Job Card Time Log", tl_name, "from_time")
            to_time_val = now_datetime()
            values = {"to_time": to_time_val}
            
            if from_time:
                time_diff = get_datetime(to_time_val) - get_datetime(from_time)
                values["time_in_mins"] = time_diff.total_seconds() / 60
            
            # اضافه کردن completed_qty به time log
            if completed_qty is not None:
                values["completed_qty"] = flt(completed_qty)
            
            frappe.db.set_value("Job Card Time Log", tl_name, values)
            return tl_name
    
    return None

@frappe.whitelist()
def get_work_orders_summary(date=None):
    """Get work orders summary with job cards status"""
    
    filters = {}
    if date:
        filters["custom_planned_end_date"] = date
    
    # Get all job cards for the date
    job_cards = frappe.get_all("Job Card",
        filters=filters,
        fields=[
            "name", "work_order", "status", "for_quantity",
            "custom_job_card_priority", "operation", "production_item"
        ]
    )
    
    # Group by work order
    work_orders_data = {}
    for jc in job_cards:
        wo_name = jc.work_order
        if wo_name not in work_orders_data:
            work_orders_data[wo_name] = {
                "name": wo_name,
                "production_item": jc.production_item,
                "job_cards": [],
                "total_cards": 0,
                "completed_cards": 0,
                "priority": jc.custom_job_card_priority or 0
            }
        
        work_orders_data[wo_name]["job_cards"].append(jc)
        work_orders_data[wo_name]["total_cards"] += 1
        
        if jc.status == "Completed":
            work_orders_data[wo_name]["completed_cards"] += 1
    
    # Calculate progress for each work order
    for wo_name, wo_data in work_orders_data.items():
        if wo_data["total_cards"] > 0:
            wo_data["progress"] = (wo_data["completed_cards"] / wo_data["total_cards"]) * 100
        else:
            wo_data["progress"] = 0
    
    return list(work_orders_data.values())

@frappe.whitelist()
def check_work_order_completion(work_order_name):
    """Check if work order is completed based on job cards"""
    
    if not work_order_name:
        return False
    
    # Get all job cards for this work order
    job_cards = frappe.get_all("Job Card",
        filters={"work_order": work_order_name},
        fields=["name", "status"]
    )
    
    if not job_cards:
        return False
    
    # Check if all job cards are completed
    completed_count = len([jc for jc in job_cards if jc.status == "Completed"])
    total_count = len(job_cards)
    
    if completed_count == total_count:
        # Update work order status atomically
        frappe.db.set_value("Work Order", work_order_name, {
            "status": "Completed",
            "actual_end_date": now_datetime()
        })
            
        return True
    
    return False

@frappe.whitelist()
def submit_job_card(job_card_name):
    """Submit a job card safely on server side"""
    if not job_card_name:
        frappe.throw(_("Job Card name is required"))
    
    # بررسی اینکه آیا کل کار تکمیل شده
    job_card = frappe.get_doc("Job Card", job_card_name)
    total_completed = sum([flt(log.completed_qty) for log in job_card.time_logs if log.completed_qty])
    
    if total_completed < job_card.for_quantity:
        frappe.throw(_("نمی‌توان کارت کار را ارسال کرد. هنوز کار تکمیل نشده است."))
    
    if job_card.docstatus == 0:
        job_card.submit()  # این status را به Submitted تغییر می‌دهد
    
    job_card.status = "Submitted"
    return {"status": "success", "name": job_card.name, "docstatus": job_card.docstatus}

@frappe.whitelist()
def get_job_card_time_summary(job_card_name):
    """Get time summary for a specific job card"""
    
    time_logs = frappe.get_all("Job Card Time Log",
        filters={"parent": job_card_name},
        fields=["employee", "from_time", "to_time", "time_in_mins", "completed_qty"],
        order_by="from_time desc"
    )
    
    total_minutes = 0
    total_completed = 0
    
    for log in time_logs:
        if log.time_in_mins:
            total_minutes += log.time_in_mins
        if log.completed_qty:
            total_completed += log.completed_qty

    total_hours = total_minutes / 60
    
    return {
        "time_logs": time_logs,
        "total_hours": total_hours,
        "total_minutes": total_minutes,
        "total_completed_qty": total_completed,
        "formatted_time": f"{int(total_hours)}:{int((total_minutes % 60)):02d}"
    }

@frappe.whitelist()
def get_job_card_completed_qty(job_card_name):
    """Get total completed quantity from time logs"""
    
    time_logs = frappe.get_all("Job Card Time Log",
        filters={"parent": job_card_name},
        fields=["completed_qty"]
    )
    
    total_completed = sum([log.completed_qty or 0 for log in time_logs])
    
    return {
        "completed_qty": total_completed,
    }

@frappe.whitelist()
def get_employee_productivity(employee=None, date_from=None, date_to=None):
    """Get employee productivity statistics"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
    
    filters = {"employee": employee}
    
    if date_from:
        filters["from_time"] = [">=", date_from]
    
    if date_to:
        filters["to_time"] = ["<=", date_to]
    
    # Get time logs
    time_logs = frappe.get_all("Job Card Time Log",
        filters=filters,
        fields=["parent", "from_time", "to_time", "time_in_mins", "completed_qty"]
    )
    
    # Calculate statistics
    total_job_cards = len(set([log.parent for log in time_logs]))
    total_minutes = sum([log.time_in_mins or 0 for log in time_logs])
    total_hours = total_minutes / 60
    total_produced = sum([log.completed_qty or 0 for log in time_logs])
    
    # Get completed job cards
    completed_job_cards = frappe.get_all("Job Card",
        filters={
            "status": "Completed",
            "actual_end_date": ["between", [date_from or "2000-01-01", date_to or "2099-12-31"]]
        },
        fields=["name", "for_quantity"]
    )
    
    completed_count = len(completed_job_cards)
    total_planned = sum([jc.for_quantity or 0 for jc in completed_job_cards])
    
    return {
        "total_job_cards_worked": total_job_cards,
        "completed_job_cards": completed_count,
        "total_work_hours": total_hours,
        "total_work_minutes": total_minutes,
        "total_completed_qty": total_produced,
        "total_planned_qty": total_planned,
        "efficiency": (total_produced / total_planned * 100) if total_planned > 0 else 0,
        "formatted_work_time": f"{int(total_hours)}:{int((total_minutes % 60)):02d}"
    }

@frappe.whitelist()
def switch_job_card(from_job_card, to_job_card, employee=None):
    """Switch from one job card to another"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
    
    # Pause current job card
    if from_job_card:
        pause_job_card(from_job_card, employee)
    
    # Start new job card
    result = start_job_card(to_job_card, employee)
    
    return {
        "status": "success",
        "message": _("Successfully switched to new job card"),
        "from_job_card": from_job_card,
        "to_job_card": to_job_card
    }

@frappe.whitelist()
def get_workstation_queue(workstation=None, date=None):
    """Get job cards queue for a workstation"""
    
    if not workstation:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["workstation"]
        )
        if employee_doc:
            workstation = employee_doc[0].workstation
        else:
            frappe.throw(_("No workstation found for current user"))
    
    filters = {
        "workstation_type": workstation,
        "status": ["!=", "Completed"]
    }
    
    if date:
        filters["custom_planned_end_date"] = date
    
    job_cards = frappe.get_all("Job Card",
        filters=filters,
        fields=[
            "name", "operation", "work_order", "production_item",
            "status", "custom_job_card_priority", "idx", "sequence_id",
            "custom_planned_start_date", "custom_planned_end_date",
            "for_quantity"
        ],
        order_by="custom_job_card_priority desc, sequence_id asc, idx asc"
    )
    
    return job_cards

# Scheduler functions
def auto_pause_idle_job_cards():
    """Auto pause job cards that have been idle for more than specified time"""
    
    # Get all active job cards
    active_job_cards = frappe.get_all("Job Card",
        filters={"status": "Work In Progress"},
        fields=["name"]
    )
    
    idle_threshold = frappe.db.get_single_value("Manufacturing Settings", "job_card_idle_timeout") or 120  # minutes
    
    for jc in active_job_cards:
        # Check latest time log
        latest_log = frappe.get_all("Job Card Time Log",
            filters={
                "parent": jc.name,
                "to_time": ["is", "not set"]
            },
            fields=["name", "from_time", "employee"],
            order_by="creation desc",
            limit=1
        )
        
        if latest_log:
            log = latest_log[0]
            time_diff = datetime.now() - get_datetime(log.from_time)
            
            if time_diff.total_seconds() / 60 > idle_threshold:
                # Auto pause the job card
                pause_job_card(jc.name, log.employee)
                
                # Send notification
                frappe.sendmail(
                    recipients=[frappe.get_value("Employee", log.employee, "user_id")],
                    subject=_("Job Card Auto Paused"),
                    message=_("Job Card {0} has been automatically paused due to inactivity").format(jc.name)
                )

import frappe
from frappe import _
from frappe.utils import nowdate

@frappe.whitelist()
def send_daily_productivity_report():
    """Send daily productivity report to supervisors"""
    
    # دریافت همه کارمندهای فعال
    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "user_id", "reports_to"]
    )
    
    date_today = nowdate()
    
    for emp in employees:
        if emp.user_id:
            productivity = get_employee_productivity(
                employee=emp.name,
                date_from=date_today,
                date_to=date_today
            )
            
            if productivity.get("total_job_cards_worked", 0) > 0:
                # ارسال گزارش به سرپرست
                if emp.reports_to:
                    supervisor_email = frappe.get_value("Employee", emp.reports_to, "user_id")
                    if supervisor_email:
                        frappe.sendmail(
                            recipients=[supervisor_email],
                            subject=_("Daily Productivity Report - {0}").format(emp.employee_name),
                            message=f"""
                                <h3>Daily Productivity Report for {emp.employee_name}</h3>
                                <p><strong>Date:</strong> {date_today}</p>
                                <p><strong>Job Cards Worked:</strong> {productivity['total_job_cards_worked']}</p>
                                <p><strong>Completed Job Cards:</strong> {productivity['completed_job_cards']}</p>
                                <p><strong>Total Work Hours:</strong> {productivity['formatted_work_time']}</p>
                                <p><strong>Production Efficiency:</strong> {productivity['efficiency']:.1f}%</p>
                            """
                        )
                        
@frappe.whitelist()
def pause_job_card(job_card_name, completed_qty=0, remarks="", employee=None):
    """Pause a job card and update active time log for the current employee"""

    if not job_card_name:
        frappe.throw(_("Job Card نامعتبر است"))

    # پیدا کردن کارمند لاگین‌شده
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name

    # گرفتن Job Card
    job_card = frappe.get_doc("Job Card", job_card_name)

    # پیدا کردن time_log فعال همین کارمند
    active_time_log = None
    for log in reversed(job_card.time_logs):
        if log.employee == employee and not log.to_time:
            active_time_log = log
            break

    if not active_time_log:
        frappe.throw(_("هیچ لاگ فعالی برای این کارمند پیدا نشد"))

    # تبدیل مقادیر به float
    try:
        completed_qty = float(completed_qty) if completed_qty else 0.0
    except (ValueError, TypeError):
        completed_qty = 0.0

    # آپدیت مقادیر time_log فعال
    active_time_log.to_time = now_datetime()
    active_time_log.completed_qty = completed_qty
    active_time_log.remarks = remarks

    # محاسبه time_in_mins
    if active_time_log.from_time:
        time_diff = get_datetime(active_time_log.to_time) - get_datetime(active_time_log.from_time)
        active_time_log.time_in_mins = time_diff.total_seconds() / 60

    # تغییر وضعیت Job Card به Paused
    job_card.status = "Paused"
    job_card.save()
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Job Card {0} متوقف شد").format(job_card_name)
    }

@frappe.whitelist()
def complete_job_card(job_card_name, completed_qty=0, remarks="", employee=None):
    """
    تکمیل یک Job Card با بروزرسانی رکورد فعال time_log همان کارمند
    ولی status را به Completed تغییر نمی‌دهد، فقط time log را بسته می‌کند
    """
    if not job_card_name:
        frappe.throw(_("Job Card نامعتبر است"))

    if not employee:
        employee_doc = frappe.get_all("Employee",
            filters={"user_id": frappe.session.user},
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name

    job_card = frappe.get_doc("Job Card", job_card_name)

    # برای تکمیل باید حتماً مقدار بیشتر از صفر باشد
    try:
        completed_qty = float(completed_qty)
        if completed_qty <= 0:
            frappe.throw(_("تعداد تکمیل شده باید بیشتر از صفر باشد"))
    except (ValueError, TypeError):
        frappe.throw(_("تعداد تکمیل شده معتبر نیست"))

    # پیدا کردن رکورد فعال time_log همان کارمند
    active_time_log = None
    for log in reversed(job_card.time_logs):
        if log.employee == employee and not log.to_time:
            active_time_log = log
            break

    if not active_time_log:
        frappe.throw(_("No active time log found for this employee"))

    # بروزرسانی رکورد time_log فعال (بدون اضافه کردن رکورد جدید)
    active_time_log.to_time = now_datetime()
    active_time_log.completed_qty = completed_qty
    active_time_log.remarks = remarks

    total_completed = sum([flt(log.completed_qty) for log in job_card.time_logs if log.completed_qty])
    # محاسبه time_in_mins
    if active_time_log.from_time:
        time_diff = get_datetime(active_time_log.to_time) - get_datetime(active_time_log.from_time)
        active_time_log.time_in_mins = time_diff.total_seconds() / 60
        # بستن همه time log های فعال دیگر کارمندان روی همین job card
        for log in job_card.time_logs:
            if log.employee != employee and not log.to_time:
                # محاسبه باقی‌مانده برای این کارمند
                remaining_qty = max(0, job_card.for_quantity - total_completed)
                log.to_time = now_datetime()
                log.completed_qty = remaining_qty
                log.remarks = f"تکمیل خودکار - کار توسط {frappe.get_value('Employee', employee, 'employee_name')} تمام شد"
                
                # محاسبه time_in_mins برای این لاگ
                if log.from_time:
                    time_diff = get_datetime(log.to_time) - get_datetime(log.from_time)
                    log.time_in_mins = time_diff.total_seconds() / 60

    # بررسی کل تولید انجام شده

    
    if total_completed >= job_card.for_quantity:
        # اگر کل تولید کامل شد، status را به Completed تغییر بده
        job_card.actual_end_date = now_datetime()
    else:
        # اگر هنوز باقی مانده دارد، status را Open کن تا دوباره شروع شود
        job_card.status = "Open"

    job_card.actual_end_date = now_datetime()

    job_card.save()
    frappe.db.commit()

    # ایجاد GL Entry برای درآمد کارمند
    try:
        gl_result = create_gl_entry_for_job_completion(job_card_name, completed_qty)
        if gl_result.get("success"):
            # فرمت کردن مبلغ برای نمایش
            amount = gl_result.get('amount', 0)
            formatted_amount = f"{amount:,.0f} ریال"
            frappe.msgprint(f"GL Entry ایجاد شد. مبلغ: {formatted_amount}")
        elif gl_result.get("error"):
            frappe.log_error(f"خطا در ایجاد GL Entry: {gl_result.get('error')}")
    except Exception as e:
        frappe.log_error(f"خطا در فراخوانی create_gl_entry_for_job_completion: {str(e)}")

    return {"status": "success", "message": _("Job Card {0} با موفقیت تکمیل شد.").format(job_card_name)}


@frappe.whitelist()
def get_job_card_quantities(job_card_name):
    """Get job card quantities - این تابع قبلاً موجود است اما باید در انتهای فایل باشد"""
    if not job_card_name:
        return {"completed_qty": 0}
    
    time_logs = frappe.get_all("Job Card Time Log",
        filters={"parent": job_card_name},
        fields=["completed_qty"]
    )
    
    total_completed = sum([flt(log.completed_qty) for log in time_logs])
    return {
        "completed_qty": total_completed,
        "total_produced": total_completed   
    }

@frappe.whitelist()
def get_active_job_employee(job_card_name):
    """Get all employees currently working on a job card"""
    if not job_card_name:
        return None
    
    # Get all active time logs without to_time
    active_logs = frappe.get_all("Job Card Time Log",
        filters={
            "parent": job_card_name,
            "to_time": ["is", "not set"]
        },
        fields=["employee"],
        order_by="creation desc"
    )
    
    if active_logs:
        employees = []
        for log in active_logs:
            employee_name = frappe.get_value("Employee", log.employee, "employee_name")
            employees.append({
                "employee": log.employee,
                "employee_name": employee_name
            })
        return employees
    
    return None


@frappe.whitelist()
def can_employee_control_job(job_card_name, employee=None):
    """Check if employee can control this job card (start/pause/complete)"""
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            return False
        employee = employee_doc[0].name
    
    # Check if this employee has the active time log for this job card
    active_log = frappe.get_all("Job Card Time Log",
        filters={
            "parent": job_card_name,
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        fields=["name"],
        limit=1
    )
    
    return len(active_log) > 0

@frappe.whitelist()
def get_production_item_dependencies(production_item, work_order=None):
    """Get BOM dependencies for a production item that need to be produced"""
    
    # Get BOM for this production item
    bom = frappe.get_value("BOM", {"item": production_item, "is_active": 1}, "name")
    if not bom:
        return []
    
    # Get BOM items (dependencies)
    bom_items = frappe.get_all("BOM Item",
        filters={"parent": bom},
        fields=["item_code", "qty"]
    )
    
    dependencies = []
    for item in bom_items:
        # بررسی کنیم که آیا این آیتم باید تولید شود یا نه
        # اگر آیتم خود یک کالای تولیدی است (BOM دارد) و در همین work order تولید می‌شود
        if is_production_item(item.item_code) and is_in_work_order(item.item_code, work_order):
            dependencies.append(item.item_code)
    
    return dependencies

def is_production_item(item_code):
    """Check if item has an active BOM (is a production item)"""
    bom = frappe.get_value("BOM", {"item": item_code, "is_active": 1}, "name")
    return bool(bom)

def is_in_work_order(item_code, work_order):
    """Check if item is being produced in this work order"""
    if not work_order:
        return False
        
    # بررسی کنیم که آیا برای این آیتم job card در این work order وجود دارد
    job_cards = frappe.get_all("Job Card",
        filters={
            "work_order": work_order,
            "production_item": item_code
        },
        fields=["name"]
    )
    
    return len(job_cards) > 0

@frappe.whitelist()
def check_production_dependencies(job_card_name):
    """Check if all production dependencies are completed"""
    
    job_card = frappe.get_doc("Job Card", job_card_name)
    work_order = job_card.work_order
    production_item = job_card.production_item
    
    # Get dependencies for this production item
    dependencies = get_production_item_dependencies(production_item, work_order)
    
    if not dependencies:
        return True  # No dependencies, can start
    
    # Check if dependent production items are completed in this work order
    for dep_item in dependencies:
        # Get all job cards for dependent item in same work order
        dep_job_cards = frappe.get_all("Job Card",
            filters={
                "work_order": work_order,
                "production_item": dep_item
            },
            fields=["name", "status"]
        )
        
        # اگر هیچ job card ای برای dependency وجود نداشت، یعنی مشکل هست
        if not dep_job_cards:
            frappe.log_error(f"No job cards found for dependency {dep_item} in work order {work_order}")
            return False
        
        # بررسی کنیم که همه job card های مربوط به dependency تکمیل شده باشند
        for dep_job_card in dep_job_cards:
            if dep_job_card.status not in ["Completed", "Submitted"]:
                return False  # Dependency not completed
    
    return True  # All dependencies completed

@frappe.whitelist()
def get_all_production_dependencies(work_order):
    """Get complete dependency tree for all items in work order"""
    
    # Get all job cards in this work order
    job_cards = frappe.get_all("Job Card",
        filters={"work_order": work_order},
        fields=["name", "production_item", "status"]
    )
    
    dependency_map = {}
    
    # Build dependency map
    for job_card in job_cards:
        item = job_card.production_item
        dependencies = get_production_item_dependencies(item, work_order)
        dependency_map[item] = dependencies
    
    return dependency_map

@frappe.whitelist()
def get_nested_orders_data(date_filter=None, status_filter=None, workstation_filter=None, workstation_type_filter=None, current_user=None):
    """
    دریافت کامل داده‌های nested orders در یک query
    """
    
    # دریافت اطلاعات کارمند فعلی
    current_employee = None
    if current_user:
        emp_data = frappe.get_all("Employee", 
            filters={"user_id": current_user}, 
            fields=["name", "employee_name", "workstation"],
            limit=1
        )
        if emp_data:
            current_employee = emp_data[0]
    
    # ساخت فیلترهای Job Card
    job_card_filters = {"status": ["not in", ["Cancelled"]]}
    
    if status_filter:
        job_card_filters["status"] = status_filter
    
    if date_filter:
        job_card_filters["custom_planned_end_date"] = date_filter
    
    # منطق فیلتر workstation
    workstation_type = None
    if workstation_type_filter:
        workstation_type = workstation_type_filter
    elif workstation_filter:
        workstation_type = frappe.get_value("Workstation", workstation_filter, "workstation_type")
    elif current_employee and current_employee.get("workstation"):
        workstation_type = frappe.get_value("Workstation", current_employee["workstation"], "workstation_type")
    
    if workstation_type:
        job_card_filters["workstation_type"] = workstation_type
    
    # دریافت Job Cards
    job_cards = frappe.get_all("Job Card",
        filters=job_card_filters,
        fields=[
            "name", "production_item", "operation", "status", "for_quantity",
            "work_order", "workstation_type", "idx", "sequence_id",
            "custom_planned_start_date", "custom_planned_end_date",
            "expected_start_date", "expected_end_date", "time_required",
            "actual_start_date", "actual_end_date"
        ],
        order_by="work_order asc, sequence_id asc, idx asc",
        limit=500
    )
    
    if not job_cards:
        return {"grouped_data": {}, "current_employee": current_employee, "active_job": None}
    
    # دریافت Work Orders
    work_order_names = list(set([jc["work_order"] for jc in job_cards if jc["work_order"]]))
    work_orders = {}
    if work_order_names:
        wo_data = frappe.get_all("Work Order",
            filters={"name": ["in", work_order_names]},
            fields=["name", "status", "qty", "sales_order", "production_item", "bom_no"]
        )
        for wo in wo_data:
            work_orders[wo["name"]] = wo
    
    # دریافت Sales Orders
    sales_order_names = list(set([wo["sales_order"] for wo in work_orders.values() if wo.get("sales_order")]))
    sales_orders = {}
    if sales_order_names:
        so_data = frappe.get_all("Sales Order",
            filters={"name": ["in", sales_order_names]},
            fields=["name", "customer", "delivery_date", "status", "sales_order_priority"]
        )
        for so in so_data:
            sales_orders[so["name"]] = so
    
    # دریافت BOM Data
    bom_names = list(set([wo["bom_no"] for wo in work_orders.values() if wo.get("bom_no")]))
    bom_data = {}
    if bom_names:
        bom_list = frappe.get_all("BOM",
            filters={"name": ["in", bom_names]},
            fields=["name", "item", "quantity"]
        )
        for bom in bom_list:
            bom_data[bom["name"]] = bom
    
    # دریافت Employees
    employee_data = {}
    emp_list = frappe.get_all("Employee",
        fields=["name", "employee_name", "user_id"],
        limit=500
    )
    for emp in emp_list:
        employee_data[emp["name"]] = emp
    
    # الصاق محاسبات قیمت به هر Job Card
    for jc in job_cards:
        try:
            pricing = _compute_job_card_pricing(jc)
            jc.update({
                "hour_rate_electricity": pricing.get("hour_rate_electricity", 0),
                "hour_rate_consumable": pricing.get("hour_rate_consumable", 0),
                "hour_rate_rent": pricing.get("hour_rate_rent", 0),
                "hour_rate_labour": pricing.get("hour_rate_labour", 0),
                "net_hour_rate": pricing.get("net_hour_rate", 0),
                "minutes_per_unit": pricing.get("minutes_per_unit", 0),
                "effective_hour_rate": pricing.get("effective_hour_rate", 0),
                "per_unit_price": pricing.get("per_unit_price", 0),
                "total_price": pricing.get("total_price", 0),
            })
        except Exception:
            # در صورت بروز خطا، چیزی اضافه نمی‌کنیم
            pass

    # گروه‌بندی nested
    grouped_data = {}
    for jc in job_cards:
        work_order = work_orders.get(jc["work_order"])
        sales_order_name = work_order.get("sales_order") if work_order else "بدون سفارش فروش"
        work_order_name = jc["work_order"] or "نامشخص"
        production_item = jc["production_item"] or "نامشخص"
        
        if sales_order_name not in grouped_data:
            grouped_data[sales_order_name] = {}
        
        if work_order_name not in grouped_data[sales_order_name]:
            grouped_data[sales_order_name][work_order_name] = {}
        
        if production_item not in grouped_data[sales_order_name][work_order_name]:
            grouped_data[sales_order_name][work_order_name][production_item] = []
        
        grouped_data[sales_order_name][work_order_name][production_item].append(jc)
    
    # دریافت Active Job
    active_job = None
    if current_employee and current_employee.get("workstation"):
        workstation_type = frappe.get_value("Workstation", current_employee["workstation"], "workstation_type")
        if workstation_type:
            active_jobs = frappe.get_all("Job Card",
                filters={
                    "workstation_type": workstation_type,
                    "status": "Work In Progress"
                },
                fields=["name", "operation"],
                limit=1
            )
            if active_jobs:
                active_job = active_jobs[0]
    
    return {
        "grouped_data": grouped_data,
        "sales_orders": sales_orders,
        "work_orders": work_orders,
        "bom_data": bom_data,
        "employee_data": employee_data,
        "current_employee": current_employee,
        "active_job": active_job
    }

@frappe.whitelist()
def get_job_cards_with_quantities():
    """
    دریافت تمام job cards همراه با مقادیر تکمیل شده
    """
    
    # دریافت تمام Job Cards با time logs در یک query
    job_cards_with_qty = frappe.db.sql("""
        SELECT 
            jc.name,
            jc.for_quantity,
            jc.status,
            COALESCE(SUM(jctl.completed_qty), 0) as completed_qty
        FROM 
            `tabJob Card` jc
        LEFT JOIN 
            `tabJob Card Time Log` jctl ON jc.name = jctl.parent
        WHERE 
            jc.status != 'Cancelled'
        GROUP BY 
            jc.name, jc.for_quantity, jc.status
    """, as_dict=True)
    
    result = {}
    for jc in job_cards_with_qty:
        result[jc["name"]] = {
            "completed_qty": jc["completed_qty"],
            "for_quantity": jc["for_quantity"],
            "status": jc["status"],
            "remaining_qty": max(0, jc["for_quantity"] - jc["completed_qty"]),
            "should_show_submit": (jc["completed_qty"] >= jc["for_quantity"])
        }
    
    return result

@frappe.whitelist()
def get_employee_accounting_data(employee=None):
    """
    دریافت اطلاعات حسابداری کارمند
    """
    import json
    
    # Parse employee data if it's a JSON string
    if employee and isinstance(employee, str):
        try:
            employee_data = json.loads(employee)
            employee = employee_data.get("name")
        except (json.JSONDecodeError, AttributeError):
            # If it's not JSON, assume it's already the employee name
            pass
    
    if not employee:
        # دریافت کارمند فعلی
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            return {"error": "کارمند یافت نشد"}
        employee = employee_doc[0]["name"]
    
    # محاسبه کل درآمد از Job Card Time Logs
    total_earnings = frappe.db.sql("""
        SELECT COALESCE(SUM(
            CASE 
                WHEN jctl.completed_qty > 0 AND jc.for_quantity > 0 AND jc.time_required > 0
                THEN jctl.completed_qty * (jc.time_required / jc.for_quantity / 60.0) * 
                     (2.0/3.0) * COALESCE(ws.net_hour_rate, 0)
                ELSE 0
            END
        ), 0) as total_earnings
        FROM `tabJob Card Time Log` jctl
        INNER JOIN `tabJob Card` jc ON jc.name = jctl.parent
        LEFT JOIN (
            SELECT workstation_type,
                   SUM(COALESCE(hour_rate_electricity, 0) + 
                       COALESCE(hour_rate_consumable, 0) + 
                       COALESCE(hour_rate_rent, 0) + 
                       COALESCE(hour_rate_labour, 0)) as net_hour_rate
            FROM `tabWorkstation`
            GROUP BY workstation_type
        ) ws ON ws.workstation_type = jc.workstation_type
        WHERE jctl.employee = %s
    """, (employee,), as_dict=True)
    
    total_earnings = total_earnings[0].get("total_earnings", 0) if total_earnings else 0
    
    # رند کردن به نزدیکترین ۵۰ هزار ریال
    total_earnings = round(total_earnings / 50000) * 50000
    
    # دریافت حساب‌های داینامیک
    accounts = get_manufacturing_accounts()
    payable_account = accounts["payable_account"]
    
    # محاسبه پرداخت‌های انجام شده (از GL Entry)
    total_paid = frappe.db.sql("""
        SELECT COALESCE(SUM(credit), 0) as total_paid
        FROM `tabGL Entry`
        WHERE party_type = 'Employee' 
        AND party = %s
        AND (account = %s OR account LIKE %s)
    """, (employee, payable_account, '%حقوق و دستمزد پرداختنی%'), as_dict=True)
    
    total_paid = total_paid[0].get("total_paid", 0) if total_paid else 0
    
    # محاسبه مانده
    balance = total_earnings - total_paid
    
    # درآمدهای اخیر
    recent_earnings = frappe.db.sql("""
        SELECT 
            jctl.parent as job_card,
            DATE(jctl.from_time) as date,
            CASE 
                WHEN jctl.completed_qty > 0 AND jc.for_quantity > 0 AND jc.time_required > 0
                THEN jctl.completed_qty * (jc.time_required / jc.for_quantity / 60.0) * 
                     (2.0/3.0) * COALESCE(ws.net_hour_rate, 0)
                ELSE 0
            END as amount
        FROM `tabJob Card Time Log` jctl
        INNER JOIN `tabJob Card` jc ON jc.name = jctl.parent
        LEFT JOIN (
            SELECT workstation_type,
                   SUM(COALESCE(hour_rate_electricity, 0) + 
                       COALESCE(hour_rate_consumable, 0) + 
                       COALESCE(hour_rate_rent, 0) + 
                       COALESCE(hour_rate_labour, 0)) as net_hour_rate
            FROM `tabWorkstation`
            GROUP BY workstation_type
        ) ws ON ws.workstation_type = jc.workstation_type
        WHERE jctl.employee = %s
        AND jctl.completed_qty > 0
        ORDER BY jctl.from_time DESC
        LIMIT 20
    """, (employee,), as_dict=True)
    
    # رند کردن درآمدها
    for earning in recent_earnings:
        earning["amount"] = round(earning["amount"] / 50000) * 50000
    
    # پرداخت‌های اخیر
    recent_payments = frappe.db.sql("""
        SELECT 
            voucher_no as reference,
            posting_date as date,
            credit as amount
        FROM `tabGL Entry`
        WHERE party_type = 'Employee' 
        AND party = %s
        AND (account = %s OR account LIKE %s)
        AND credit > 0
        ORDER BY posting_date DESC, creation DESC
        LIMIT 20
    """, (employee, payable_account, '%حقوق و دستمزد پرداختنی%'), as_dict=True)
    
    # آمار تفصیلی برای کارگر
    stats = {
        "total_job_cards": len(recent_earnings),
        "avg_earning_per_job": total_earnings / len(recent_earnings) if recent_earnings else 0,
        "total_payments": len(recent_payments),
        "last_payment_date": recent_payments[0]["date"] if recent_payments else None,
        "last_earning_date": recent_earnings[0]["date"] if recent_earnings else None
    }
    
    # پیام‌های توضیحی برای کارگر
    messages = []
    
    if balance > 0:
        messages.append(f"💰 شما {balance:,.0f} ریال طلب دارید که هنوز پرداخت نشده است.")
    elif balance < 0:
        messages.append(f"⚠️ شما {abs(balance):,.0f} ریال بدهی دارید.")
    else:
        messages.append("✅ حساب شما تسویه است.")
    
    if recent_earnings:
        messages.append(f"📊 در {len(recent_earnings)} کار اخیر، مجموع {total_earnings:,.0f} ریال درآمد کسب کرده‌اید.")
    
    if recent_payments:
        messages.append(f"💳 آخرین پرداخت در تاریخ {recent_payments[0]['date']} به مبلغ {recent_payments[0]['amount']:,.0f} ریال بوده است.")
    
    return {
        "total_earnings": total_earnings,
        "total_paid": total_paid,
        "balance": balance,
        "recent_earnings": recent_earnings,
        "recent_payments": recent_payments,
        "stats": stats,
        "messages": messages,
        "employee_name": employee,
        "summary": {
            "total_earnings_formatted": f"{total_earnings:,.0f} ریال",
            "total_paid_formatted": f"{total_paid:,.0f} ریال", 
            "balance_formatted": f"{balance:,.0f} ریال",
            "balance_status": "طلب" if balance > 0 else "بدهی" if balance < 0 else "تسویه"
        }
    }

def get_manufacturing_accounts():
    """
    دریافت حساب‌های مربوط به تولید از Manufacturing Settings
    """
    try:
        settings = frappe.get_single("Manufacturing Settings")
        
        # دریافت حساب حقوق و دستمزد پرداختنی
        payable_account = settings.get("employee_wages_payable_account")
        if not payable_account:
            # اگر در تنظیمات تعریف نشده، از حساب پیش‌فرض استفاده کن
            payable_account = "حقوق و دستمزد پرداختنی - کارمندان"
        
        # دریافت حساب هزینه دستمزد تولید
        expense_account = settings.get("production_wages_expense_account")
        if not expense_account:
            # اگر در تنظیمات تعریف نشده، از حساب پیش‌فرض استفاده کن
            expense_account = "هزینه دستمزد تولید"
        
        return {
            "payable_account": payable_account,
            "expense_account": expense_account
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت حساب‌های تولید: {str(e)}")
        # در صورت خطا، حساب‌های پیش‌فرض را برگردان
        return {
            "payable_account": "حقوق و دستمزد پرداختنی - کارمندان",
            "expense_account": "هزینه دستمزد تولید"
        }

@frappe.whitelist()
def create_gl_entry_for_job_completion(job_card_name, completed_qty):
    """
    ایجاد GL Entry برای تکمیل کارت کار
    """
    try:
        # دریافت اطلاعات کارت کار
        job_card = frappe.get_doc("Job Card", job_card_name)
        if not job_card:
            return {"error": "کارت کار یافت نشد"}
        
        # محاسبه مبلغ
        pricing = _compute_job_card_pricing({
            "for_quantity": job_card.for_quantity,
            "time_required": job_card.time_required,
            "workstation_type": job_card.workstation_type,
        })
        
        per_unit_price = flt(pricing.get("per_unit_price") or 0)
        total_amount = flt(completed_qty) * per_unit_price
        
        # رند کردن به نزدیکترین ۵۰ هزار ریال
        total_amount = round(total_amount / 50000) * 50000
        
        if total_amount <= 0:
            return {"error": "مبلغ محاسبه شده صفر است"}
        
        # دریافت کارمند از Time Log
        employee = frappe.db.get_value("Job Card Time Log", 
            {"parent": job_card_name, "completed_qty": [">", 0]}, 
            "employee")
        
        if not employee:
            return {"error": "کارمند یافت نشد"}
        
        # دریافت حساب‌های داینامیک از Manufacturing Settings
        accounts = get_manufacturing_accounts()
        payable_account = accounts["payable_account"]
        expense_account = accounts["expense_account"]
        
        # ایجاد GL Entry
        gl_entry = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": frappe.utils.today(),
            "account": payable_account,  # حساب داینامیک از تنظیمات
            "party_type": "Employee",
            "party": employee,
            "debit": total_amount,
            "credit": 0,
            "debit_in_account_currency": total_amount,
            "credit_in_account_currency": 0,
            "against": expense_account,  # حساب مقابل داینامیک
            "voucher_type": "Job Card",
            "voucher_no": job_card_name,
            "remarks": f"درآمد کارت کار {job_card_name} - تعداد: {completed_qty}",
            "is_opening": "No",
            "company": frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        })
        
        gl_entry.insert(ignore_permissions=True)
        gl_entry.submit()
        
        # ایجاد GL Entry مقابل
        gl_entry_contra = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": frappe.utils.today(),
            "account": expense_account,  # حساب هزینه داینامیک
            "debit": 0,
            "credit": total_amount,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": total_amount,
            "against": employee,
            "voucher_type": "Job Card",
            "voucher_no": job_card_name,
            "remarks": f"هزینه دستمزد کارت کار {job_card_name} - حساب: {payable_account}",
            "is_opening": "No",
            "company": frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        })
        
        gl_entry_contra.insert(ignore_permissions=True)
        gl_entry_contra.submit()
        
        return {
            "success": True,
            "amount": total_amount,
            "gl_entries": [gl_entry.name, gl_entry_contra.name]
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در ایجاد GL Entry: {str(e)}")
        return {"error": f"خطا در ایجاد GL Entry: {str(e)}"}

@frappe.whitelist()
def get_workstations_data():
    """
    دریافت اطلاعات workstation ها
    """
    workstations = frappe.get_all("Workstation",
        fields=["name", "workstation_type"],
        order_by="name asc"
    )
    
    workstation_types = list(set([ws["workstation_type"] for ws in workstations if ws["workstation_type"]]))
    
    return {
        "workstations": workstations,
        "workstation_types": workstation_types
    }

@frappe.whitelist()
def get_current_working_employees():
    """
    دریافت کارمندانی که در حال حاضر روی job card کار می‌کنند
    """
    
    working_employees = frappe.db.sql("""
        SELECT 
            jctl.parent as job_card_name,
            jctl.employee,
            emp.employee_name
        FROM 
            `tabJob Card Time Log` jctl
        INNER JOIN 
            `tabEmployee` emp ON jctl.employee = emp.name
        WHERE 
            jctl.to_time IS NULL
        ORDER BY 
            jctl.creation DESC
    """, as_dict=True)
    
    result = {}
    for we in working_employees:
        result[we["job_card_name"]] = we["employee_name"]
    
    return result

@frappe.whitelist()
def check_multiple_job_dependencies(job_card_names):
    """
    بررسی وابستگی‌های متعدد job card ها در یک query
    """
    if not job_card_names:
        return {}
    
    if isinstance(job_card_names, str):
        import json
        job_card_names = json.loads(job_card_names)
    
    results = {}
    
    for job_card_name in job_card_names:
        # بررسی وابستگی‌های تولیدی
        dependency_check = check_production_dependencies(job_card_name)
        can_start = dependency_check 
        if dependency_check:
            pass
        results[job_card_name] = can_start
    
    return results

@frappe.whitelist()  
def bulk_update_job_card_data(job_card_names):
    """
    بروزرسانی گروهی اطلاعات job card ها
    """
    if not job_card_names:
        return {}
    
    if isinstance(job_card_names, str):
        import json
        job_card_names = json.loads(job_card_names)
    
    # دریافت اطلاعات جدید
    updated_data = frappe.get_all("Job Card",
        filters={"name": ["in", job_card_names]},
        fields=[
            "name", "status", "for_quantity", "actual_start_date", 
            "actual_end_date", "production_item", "operation"
        ]
    )
    
    # دریافت مقادیر تکمیل شده
    quantities = frappe.db.sql("""
        SELECT 
            parent as job_card_name,
            COALESCE(SUM(completed_qty), 0) as completed_qty
        FROM 
            `tabJob Card Time Log`
        WHERE 
            parent IN ({})
        GROUP BY 
            parent
    """.format(','.join(['%s'] * len(job_card_names))), job_card_names, as_dict=True)
    
    # ترکیب داده‌ها
    result = {}
    quantities_dict = {q["job_card_name"]: q["completed_qty"] for q in quantities}
    
    for jc in updated_data:
        completed_qty = quantities_dict.get(jc["name"], 0)
        result[jc["name"]] = {
            "status": jc["status"],
            "for_quantity": jc["for_quantity"],
            "completed_qty": completed_qty,
            "should_show_submit": (completed_qty >= jc["for_quantity"]),
            "remaining_qty": max(0, jc["for_quantity"] - completed_qty),
            "production_item": jc["production_item"],
            "operation": jc["operation"]
        }
    
    return result



@frappe.whitelist()
def get_all_active_jobs():
    """Get all currently active job cards with employee info"""
    
    active_jobs = frappe.db.sql("""
        SELECT 
            jc.name,
            jc.operation,
            jc.production_item,
            jctl.employee,
            emp.employee_name,
            jctl.from_time,
            TIMESTAMPDIFF(MINUTE, jctl.from_time, NOW()) as duration_minutes
        FROM 
            `tabJob Card` jc
        INNER JOIN 
            `tabJob Card Time Log` jctl ON jc.name = jctl.parent
        INNER JOIN 
            `tabEmployee` emp ON jctl.employee = emp.name
        WHERE 
            jc.status = 'Work In Progress'
            AND jctl.to_time IS NULL
        ORDER BY 
            jctl.from_time DESC
    """, as_dict=True)
    
    for job in active_jobs:
        if job.duration_minutes:
            hours = job.duration_minutes // 60
            minutes = job.duration_minutes % 60
        else:
            hours = 0
            minutes = 0
        job['duration'] = f"{hours}:{minutes:02d}"
        job['start_time'] = job.from_time.strftime("%H:%M") if job.from_time else "--:--"
    
    return active_jobs



@frappe.whitelist()
def force_start_job_card(job_card_name, employee=None):
    """Force start job card without checking for active jobs"""
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
    
    # Start without checking active jobs
    frappe.db.set_value("Job Card", job_card_name, {
        "status": "Work In Progress",
        "actual_start_date": now_datetime()
    })
    
    create_time_log_entry(job_card_name, employee, "start")
    frappe.db.commit()
    
    return {"status": "success", "message": _("Job Card started successfully")}


@frappe.whitelist()
def join_job_card_work(job_card_name, employee=None):
    """Join an existing job card work"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
    
    # بررسی که job card در حال کار هست
    job_card = frappe.get_doc("Job Card", job_card_name)
    if job_card.status != "Work In Progress":
        return {"status": "error", "message": "این کارت کار در حال انجام نیست"}
    
    # بررسی که این کارمند قبلاً time log فعال نداشته باشه
    existing_log = frappe.get_all("Job Card Time Log",
        filters={
            "parent": job_card_name,
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        limit=1
    )
    
    if existing_log:
        return {"status": "error", "message": "شما در حال حاضر روی این کار کار می‌کنید"}
    
    # بررسی که کارمند روی کار دیگه‌ای کار نمی‌کنه
    other_active_logs = frappe.get_all("Job Card Time Log",
        filters={
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        fields=["parent"],
        limit=1
    )

    if other_active_logs:
        # اگر روی همین job card کار می‌کند، اجازه بده
        if other_active_logs[0].parent == job_card_name:
            return {"status": "error", "message": "شما در حال حاضر روی این کار کار می‌کنید"}
        
        # اگر روی کار دیگری کار می‌کند، confirmation بخواه
        return {
            "status": "confirm_required",
            "message": "شما روی کارت کار دیگری کار می‌کنید. آیا می‌خواهید آن را متوقف کرده و به این کار بپیوندید؟",
            "current_job": other_active_logs[0].parent
        }
    
    # ایجاد time log entry جدید
    create_time_log_entry(job_card_name, employee, "start")
    frappe.db.commit()
    
    return {"status": "success", "message": "با موفقیت به کار پیوستید"}


@frappe.whitelist()
def has_active_job(employee=None):
    """Check if employee has active job"""
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not employee_doc:
            return {"has_active": False}
        employee = employee_doc[0].name

    # بررسی وجود time log فعال
    active_logs = frappe.get_all("Job Card Time Log",
        filters={
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        limit=1
    )
    
    return {"has_active": len(active_logs) > 0}


# erpnext/manufacturing/page/orders/orders.py

@frappe.whitelist()
def get_job_complete_info(job_card_name, employee=None):
    """
    🚀 دریافت تمام اطلاعات مورد نیاز برای تولید دکمه‌های job card در یک API call
    
    Args:
        job_card_name (str): نام job card
        employee (str, optional): کارمند (اگر نداده شود از session گرفته می‌شود)
    
    Returns:
        dict: تمام اطلاعات مورد نیاز برای تصمیم‌گیری frontend
    """
    
    if not job_card_name:
        return {
            "error": "job_card_name الزامی است",
            "canControl": False,
            "workingEmployees": [],
            "hasActiveJob": False,
            "docStatus": 0,
            "shouldShowSubmit": False
        }
    
    try:
        # 🎯 تعیین کارمند فعلی
        if not employee:
            employee_doc = frappe.get_all("Employee", 
                filters={"user_id": frappe.session.user}, 
                fields=["name"],
                limit=1
            )
            if employee_doc:
                employee = employee_doc[0].name
            else:
                employee = None
        
        # 📊 دریافت اطلاعات job card
        job_card_info = frappe.get_value("Job Card", job_card_name, 
            ["docstatus", "status", "for_quantity", "total_completed_qty"], 
            as_dict=True
        )
        
        if not job_card_info:
            return {
                "error": f"Job Card {job_card_name} یافت نشد",
                "canControl": False,
                "workingEmployees": [],
                "hasActiveJob": False,
                "docStatus": 0,
                "shouldShowSubmit": False
            }
        
        # 🔍 بررسی دسترسی کنترل (آیا کارمند فعلی می‌تواند کنترل کند؟)
        canControl = False
        if employee:
            active_control_logs = frappe.get_all("Job Card Time Log",
                filters={
                    "parent": job_card_name,
                    "employee": employee,
                    "to_time": ["is", "not set"]
                },
                limit=1
            )
            canControl = len(active_control_logs) > 0
        
        # 👥 دریافت کارمندان در حال کار
        working_employees = get_working_employees_optimized(job_card_name)
        
        # ⏰ بررسی وجود کار فعال برای کارمند فعلی
        hasActiveJob = False
        if employee:
            other_active_jobs = frappe.get_all("Job Card Time Log",
                filters={
                    "employee": employee,
                    "to_time": ["is", "not set"],
                    "parent": ["!=", job_card_name]  # غیر از job card فعلی
                },
                limit=1
            )
            hasActiveJob = len(other_active_jobs) > 0
        
        # ✅ تعیین shouldShowSubmit
        shouldShowSubmit = determine_should_show_submit(job_card_info)
        
        # 📋 آماده‌سازی پاسخ نهایی
        result = {
            "canControl": canControl,
            "workingEmployees": working_employees,
            "hasActiveJob": hasActiveJob,
            "docStatus": job_card_info.get("docstatus", 0),
            "shouldShowSubmit": shouldShowSubmit,
            "jobCardStatus": job_card_info.get("status"),
            "completionInfo": {
                "forQuantity": job_card_info.get("for_quantity", 0),
                "completedQuantity": job_card_info.get("total_completed_qty", 0)
            }
        }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"خطا در get_job_complete_info: {str(e)}", "Job Card API Error")
        return {
            "error": f"خطای سیستمی: {str(e)}",
            "canControl": False,
            "workingEmployees": [],
            "hasActiveJob": False,
            "docStatus": 0,
            "shouldShowSubmit": False
        }


def get_working_employees_optimized(job_card_name):
    """
    🔄 دریافت کارمندان در حال کار روی job card (نسخه بهینه‌شده)
    
    Args:
        job_card_name (str): نام job card
    
    Returns:
        list: لیست کارمندان با اطلاعاتشان
    """
    
    # یک query برای دریافت همه اطلاعات مورد نیاز
    active_logs_with_employee_info = frappe.db.sql("""
        SELECT 
            jtl.employee,
            emp.employee_name
        FROM `tabJob Card Time Log` jtl
        LEFT JOIN `tabEmployee` emp ON jtl.employee = emp.name
        WHERE 
            jtl.parent = %s 
            AND jtl.to_time IS NULL
        ORDER BY jtl.creation DESC
    """, (job_card_name,), as_dict=True)
    
    return active_logs_with_employee_info


def determine_should_show_submit(job_card_info):
    """
    🎯 تعیین آیا دکمه Submit باید نمایش داده شود
    
    Args:
        job_card_info (dict): اطلاعات job card
    
    Returns:
        bool: True اگر باید Submit نشان داده شود
    """
    
    status = job_card_info.get("status")
    docstatus = job_card_info.get("docstatus", 0)
    for_quantity = job_card_info.get("for_quantity", 0)
    completed_qty = job_card_info.get("total_completed_qty", 0)
    
    # اگر قبلاً submitted شده
    if docstatus == 1:
        return False
    
    # اگر وضعیت Completed است
    if status == "Completed":
        return True
    
    # اگر کار کامل انجام شده (تعداد کامل تولید شده)
    if for_quantity > 0 and completed_qty >= for_quantity:
        return True
    
    return False


# 🧪 تست کردن API جدید
@frappe.whitelist()
def test_job_complete_info():
    """تست کردن API جدید برای توسعه"""
    
    # دریافت یک job card نمونه
    sample_job = frappe.get_all("Job Card", 
        fields=["name"], 
        limit=1,
        order_by="creation desc"
    )
    
    if not sample_job:
        return {"error": "هیچ Job Card یافت نشد"}
    
    job_card_name = sample_job[0].name
    result = get_job_complete_info(job_card_name)
    
    return {
        "jobCardName": job_card_name,
        "result": result,
        "message": "✅ API تست شد"
    }
    
    
    
    
    # در فایل erpnext/manufacturing/page/orders/orders.py اضافه کنید:

@frappe.whitelist()
def get_all_jobs_complete_info_bulk(job_card_names, current_user=None):
    """
    🚀 دریافت اطلاعات کامل همه Job Cards یکجا
    تاثیر: کاهش API calls از 150+ به 1
    """
    import json
    
    if isinstance(job_card_names, str):
        job_card_names = json.loads(job_card_names)
    
    if not job_card_names:
        return {}
    
    current_user = current_user or frappe.session.user
    
    try:
        # 🔥 Query اصلی - همه اطلاعات یکجا
        job_cards_query = """
            SELECT 
                jc.name,
                jc.status,
                jc.for_quantity,
                jc.docstatus,
                jc.work_order,
                jc.operation,
                jc.workstation,
                COALESCE(SUM(jctl.completed_qty), 0) as total_completed_qty,
                GROUP_CONCAT(
                    DISTINCT CASE 
                        WHEN jctl.to_time IS NULL AND jctl.employee IS NOT NULL 
                        THEN CONCAT(jctl.employee, ':', COALESCE(emp.employee_name, jctl.employee)) 
                    END 
                    SEPARATOR '|||'
                ) as working_employees
            FROM `tabJob Card` jc
            LEFT JOIN `tabJob Card Time Log` jctl ON jctl.parent = jc.name 
            LEFT JOIN `tabEmployee` emp ON emp.name = jctl.employee
            WHERE jc.name IN ({})
            GROUP BY jc.name, jc.status, jc.for_quantity, jc.docstatus, jc.work_order, jc.operation, jc.workstation
        """.format(','.join(['%s'] * len(job_card_names)))
        
        job_cards_data = frappe.db.sql(job_cards_query, job_card_names, as_dict=True)
        
        # 🔍 بررسی کارمند فعلی و Job Card فعال
        current_employee = None
        active_job_card = None
        
        # دریافت کارمند فعلی
        try:
            current_employee_data = frappe.db.get_value(
                'Employee', 
                {'user_id': current_user}, 
                ['name', 'employee_name'], 
                as_dict=True
            )
            if current_employee_data:
                current_employee = current_employee_data.get('name')
        except:
            pass
        
        # پیدا کردن Job Card فعال کارمند فعلی
        if current_employee:
            active_job_query = """
                SELECT DISTINCT jc.name, jc.operation
                FROM `tabJob Card` jc
                INNER JOIN `tabJob Card Time Log` jctl ON jctl.parent = jc.name
                WHERE jctl.employee = %s 
                AND jctl.to_time IS NULL
                AND jc.status = 'Work In Progress'
                LIMIT 1
            """
            active_job_result = frappe.db.sql(active_job_query, [current_employee], as_dict=True)
            if active_job_result:
                active_job_card = active_job_result[0].get('name')
        
        # 📊 پردازش نتایج
        result = {}
        
        for job_data in job_cards_data:
            job_name = job_data.get('name')
            status = job_data.get('status')
            for_quantity = job_data.get('for_quantity', 0)
            completed_qty = job_data.get('total_completed_qty', 0)
            working_employees_str = job_data.get('working_employees') or ''
            docstatus = job_data.get('docstatus', 0)
            
            # پردازش کارمندان در حال کار
            working_employees = []
            if working_employees_str:
                for emp_info in working_employees_str.split('|||'):
                    if emp_info and ':' in emp_info:
                        emp_code, emp_name = emp_info.split(':', 1)
                        working_employees.append({
                            'employee': emp_code,
                            'employee_name': emp_name
                        })
            
            # محاسبه باقی‌مانده
            remaining_qty = max(0, for_quantity - completed_qty)
            
            # تعیین وضعیت‌های کنترل
            can_control = False
            should_show_submit = False
            has_active_job = bool(active_job_card and active_job_card != job_name)
            
            # بررسی امکان کنترل
            if current_employee and working_employees:
                can_control = any(emp['employee'] == current_employee for emp in working_employees)
            
            # تعیین نمایش دکمه Submit
            if status == 'Completed' and docstatus == 0:
                should_show_submit = (remaining_qty <= 0)
            
            result[job_name] = {
                'name': job_name,
                'status': status,
                'for_quantity': for_quantity,
                'completed_qty': completed_qty,
                'remaining_qty': remaining_qty,
                'docstatus': docstatus,
                'canControl': can_control,
                'workingEmployees': working_employees,
                'hasActiveJob': has_active_job,
                'shouldShowSubmit': should_show_submit,
                'work_order': job_data.get('work_order'),
                'operation': job_data.get('operation'),
                'workstation': job_data.get('workstation')
            }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"خطا در get_all_jobs_complete_info_bulk: {str(e)}")
        return {}

@frappe.whitelist()
def check_multiple_job_dependencies(job_card_names):
    """
    🔍 بررسی وابستگی‌های متعدد Job Cards یکجا
    """
    import json
    
    if isinstance(job_card_names, str):
        job_card_names = json.loads(job_card_names)
    
    if not job_card_names:
        return {}
    
    try:
        # Query برای بررسی وابستگی‌ها
        dependencies_query = """
            WITH JobSequences AS (
                SELECT 
                    jc.name,
                    jc.work_order,
                    jc.production_item,
                    jc.sequence_id,
                    jc.idx,
                    jc.status,
                    COALESCE(jc.sequence_id, jc.idx, 999) as effective_sequence
                FROM `tabJob Card` jc
                WHERE jc.work_order IN (
                    SELECT DISTINCT work_order 
                    FROM `tabJob Card` 
                    WHERE name IN ({})
                )
            ),
            PreviousJobs AS (
                SELECT 
                    js1.name as current_job,
                    COUNT(js2.name) as pending_previous_jobs
                FROM JobSequences js1
                LEFT JOIN JobSequences js2 ON (
                    js2.work_order = js1.work_order 
                    AND js2.production_item = js1.production_item
                    AND js2.effective_sequence < js1.effective_sequence
                    AND js2.status NOT IN ('Completed', 'Submitted')
                )
                WHERE js1.name IN ({})
                GROUP BY js1.name
            )
            SELECT 
                pj.current_job as name,
                CASE WHEN pj.pending_previous_jobs = 0 THEN 1 ELSE 0 END as can_start
            FROM PreviousJobs pj
        """.format(
            ','.join(['%s'] * len(job_card_names)),
            ','.join(['%s'] * len(job_card_names))
        )
        
        params = job_card_names + job_card_names
        dependencies_result = frappe.db.sql(dependencies_query, params, as_dict=True)
        
        # تبدیل به dictionary
        result = {}
        for row in dependencies_result:
            result[row['name']] = bool(row['can_start'])
        
        # برای job card هایی که در نتیجه نیستند، true قرار می‌دهیم
        for job_name in job_card_names:
            if job_name not in result:
                result[job_name] = True
        
        return result
        
    except Exception as e:
        frappe.log_error(f"خطا در check_multiple_job_dependencies: {str(e)}")
        # در صورت خطا، همه را true برمی‌گردانیم
        return {job_name: True for job_name in job_card_names}

@frappe.whitelist()
def bulk_update_job_card_data(job_card_names):
    """
    🔄 بروزرسانی گروهی داده‌های Job Card
    """
    import json
    
    if isinstance(job_card_names, str):
        job_card_names = json.loads(job_card_names)
    
    if not job_card_names:
        return {}
    
    try:
        query = """
            SELECT 
                jc.name,
                jc.status,
                jc.for_quantity,
                jc.docstatus,
                COALESCE(SUM(jctl.completed_qty), 0) as completed_qty
            FROM `tabJob Card` jc
            LEFT JOIN `tabJob Card Time Log` jctl ON jctl.parent = jc.name
            WHERE jc.name IN ({})
            GROUP BY jc.name, jc.status, jc.for_quantity, jc.docstatus
        """.format(','.join(['%s'] * len(job_card_names)))
        
        data = frappe.db.sql(query, job_card_names, as_dict=True)
        
        result = {}
        for row in data:
            job_name = row['name']
            for_quantity = row['for_quantity'] or 0
            completed_qty = row['completed_qty'] or 0
            remaining_qty = max(0, for_quantity - completed_qty)
            
            result[job_name] = {
                'name': job_name,
                'status': row['status'],
                'completed_qty': completed_qty,
                'remaining_qty': remaining_qty,
                'should_show_submit': (
                    row['status'] == 'Completed' and 
                    row['docstatus'] == 0 and 
                    remaining_qty <= 0
                )
            }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"خطا در bulk_update_job_card_data: {str(e)}")
        return {}


def optimize_job_cards_queries():
    """
    🔧 بهینه‌سازی query ها و ایجاد index های مناسب
    """
    try:
        # Index های پیشنهادی برای بهبود performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_job_card_time_log_employee_time ON `tabJob Card Time Log` (employee, to_time)",
            "CREATE INDEX IF NOT EXISTS idx_job_card_work_order_status ON `tabJob Card` (work_order, status)",
            "CREATE INDEX IF NOT EXISTS idx_job_card_sequence ON `tabJob Card` (work_order, production_item, sequence_id, idx)",
        ]
        
        for index_query in indexes:
            try:
                frappe.db.sql(index_query)
            except Exception as e:
                # Index ممکن است از قبل وجود داشته باشد
                pass
                
    except Exception as e:
        frappe.log_error(f"خطا در optimize_job_cards_queries: {str(e)}")

# اجرای optimization هنگام import
try:
    optimize_job_cards_queries()
except:
    pass



@frappe.whitelist()
def get_employee_productivity_dashboard(employee=None, workstation=None):
    """Get complete productivity dashboard data for employee"""
    
    if not employee:
        employee_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name", "workstation"]
        )
        if not employee_doc:
            frappe.throw(_("No employee found for current user"))
        employee = employee_doc[0].name
        workstation = employee_doc[0].workstation
    
    today = nowdate()
    yesterday = frappe.utils.add_days(today, -1)
    week_ago = frappe.utils.add_days(today, -7)
    
    # کار فعال فعلی
    active_job = get_current_active_job(employee, workstation)
    
    # آمار امروز
    today_stats = get_daily_productivity_stats(employee, today)
    yesterday_stats = get_daily_productivity_stats(employee, yesterday)
    
    # محاسبه ترند
    trend = 0
    if yesterday_stats['productivity_percent'] > 0:
        trend = today_stats['productivity_percent'] - yesterday_stats['productivity_percent']
    
    today_stats['trend'] = round(trend, 1)
    
    # داده‌های نمودار (۷ روز اخیر)
    chart_data = get_productivity_chart_data(employee, week_ago, today)
    
    # کارهای تکمیل شده امروز
    today_completed = get_today_completed_jobs(employee, today)
    
    return {
        'active_job': active_job,
        'today_stats': today_stats,
        'chart_data': chart_data,
        'today_completed_jobs': today_completed
    }

@frappe.whitelist()
def get_current_active_job(employee=None, workstation=None):
    # فقط employee استفاده میشه
    if not employee:
        emp_doc = frappe.get_all("Employee", 
            filters={"user_id": frappe.session.user}, 
            fields=["name"]
        )
        if not emp_doc:
            return None
        employee = emp_doc[0].name
    
    # پیدا کردن لاگ باز برای این کارمند
    active_log = frappe.get_all("Job Card Time Log",
        filters={
            "employee": employee,
            "to_time": ["is", "not set"]
        },
        fields=["parent", "from_time"],
        order_by="creation desc",
        limit=1
    )
    
    if not active_log:
        return None
    
    job_card = active_log[0].parent
    from_time = active_log[0].from_time
    job = frappe.get_doc("Job Card", job_card)
    
    completed_qty = frappe.db.sql("""
        SELECT COALESCE(SUM(completed_qty), 0)
        FROM `tabJob Card Time Log`
        WHERE parent = %s AND employee = %s
    """, (job_card, employee))[0][0]
    
    start_time = frappe.utils.format_datetime(from_time, "HH:mm")
    duration = frappe.utils.now_datetime() - frappe.utils.get_datetime(from_time)
    hours = int(duration.total_seconds() // 3600)
    minutes = int((duration.total_seconds() % 3600) // 60)
    active_duration = f"{hours}:{minutes:02d}"
    
    return {
        'name': job.name,
        'operation': job.operation,
        'production_item': job.production_item,
        'for_quantity': job.for_quantity,
        'completed_qty': completed_qty,
        'start_time': start_time,
        'active_duration': active_duration
    }



def get_daily_productivity_stats(employee, date):
    """Get productivity stats for a specific date"""
    
    # گرفتن تایم‌لاگ‌های روز
    time_logs = frappe.db.sql("""
        SELECT 
            jctl.time_in_mins,
            jctl.completed_qty,
            jctl.parent as job_card,
            jc.time_required,
            jc.workstation_type
        FROM `tabJob Card Time Log` jctl
        INNER JOIN `tabJob Card` jc ON jc.name = jctl.parent
        WHERE jctl.employee = %(employee)s
        AND jctl.from_time BETWEEN %(start)s AND %(end)s
    """, {
        "employee": employee,
        "start": f"{date} 00:00:00",
        "end": f"{date} 23:59:59"
    }, as_dict=1)
    
    total_minutes = sum([log.time_in_mins or 0 for log in time_logs])
    total_hours = total_minutes / 60
    
    completed_jobs = len(set([log.job_card for log in time_logs if log.completed_qty]))
    actual_output = sum([log.completed_qty or 0 for log in time_logs])
    
    # بهره‌وری بر اساس زمان مورد انتظار
    expected_time = sum([log.time_required or 0 for log in time_logs if log.completed_qty])
    productivity_percent = 0
    if total_minutes > 0 and expected_time > 0:
        productivity_percent = round((expected_time / total_minutes) * 100, 1)
        # سقف 200٪ یا 300٪ هم می‌تونی بزنی اگه بخوای محدود کنی

    # محاسبه درآمد امروز براساس completed_qty و نرخ هر واحد
    earnings_today = 0
    for log in time_logs:
        qty = flt(log.get("completed_qty") or 0)
        if qty <= 0:
            continue
        # minutes per unit از time_required کل کارت و for_quantity کارت
        # باید for_quantity را برای این job card بگیریم
        jc_doc = frappe.get_value("Job Card", log.get("job_card"), ["for_quantity", "time_required", "workstation_type"], as_dict=True)
        if not jc_doc:
            continue
        pricing = _compute_job_card_pricing({
            "for_quantity": jc_doc.get("for_quantity"),
            "time_required": jc_doc.get("time_required"),
            "workstation_type": jc_doc.get("workstation_type"),
        })
        per_unit_price = flt(pricing.get("per_unit_price") or 0)
        earnings_today += qty * per_unit_price
    
    # رند کردن درآمد به نزدیکترین ۵۰ هزار ریال (۵ هزار تومان)
    earnings_today = round(earnings_today / 50000) * 50000

    return {
        'work_hours': int(total_hours),
        'work_minutes': int(total_minutes % 60),
        'completed_jobs': completed_jobs,
        'productivity_percent': productivity_percent,
        'total_output': actual_output,
        'earnings': earnings_today
    }


def get_productivity_chart_data(employee, date_from, date_to):
    """Get chart data for productivity trends"""
    dates = []
    productivity_data = []
    work_hours_data = []
    
    current_date = frappe.utils.get_datetime(date_from).date()
    end_date = frappe.utils.get_datetime(date_to).date()
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(current_date.strftime('%m/%d'))
        
        stats = get_daily_productivity_stats(employee, date_str)
        productivity_data.append(stats['productivity_percent'])
        work_hours_data.append(stats['work_hours'] + (stats['work_minutes']/60))
        
        current_date = frappe.utils.add_days(current_date, 1)
    
    return {
        'dates': dates,
        'productivity': productivity_data,
        'work_hours': work_hours_data
    }

def get_today_completed_jobs(employee, date):
    """Get completed jobs for today"""
    
    completed_jobs = frappe.db.sql("""
        SELECT 
            jc.name,
            jc.operation,
            jc.production_item,
            SUM(tl.time_in_mins) as duration_mins
        FROM `tabJob Card` jc
        INNER JOIN `tabJob Card Time Log` tl ON tl.parent = jc.name
        WHERE 
            tl.employee = %s 
            AND tl.from_time >= %s 
            AND tl.from_time <= %s
            AND jc.status = 'Completed'
        GROUP BY jc.name
        ORDER BY MAX(tl.to_time) DESC
        LIMIT 10
    """, (employee, f"{date} 00:00:00", f"{date} 23:59:59"), as_dict=True)
    
    for job in completed_jobs:
        hours = int(job.duration_mins // 60)
        minutes = int(job.duration_mins % 60)
        job['duration'] = f"{hours}:{minutes:02d}"
    
    return completed_jobs