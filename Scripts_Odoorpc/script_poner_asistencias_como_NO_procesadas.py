# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc


odoo = odoorpc.ODOO('interlogic.odoo.com', port=80)

# Login
odoo.login('mailync-interlogic-master-678474', 'israelcruz', '4rg1lC0nsult1ng')

attendance_obj = odoo.env['hr.attendance']

res = attendance_obj.search([('check_in','>=','2020-01-08 02:00:00'),('check_in','<=','2020-01-08 23:00:00')])
cant = len(res)
attendances = attendance_obj.browse(res)
cont = 0
for attendance in attendances:
    cont += 1
    print("====== %s - %s de %s ======" % (attendance.employee_id.name, cont, cant))
    if attendance.payslip_extra_id:
        print("attendance.payslip_extra_id.name: %s" % attendance.payslip_extra_id.name)
        attendance.payslip_extra_id.action_cancel()
    if attendance.holiday_id:
        print("attendance.holiday_id.display_name: %s" % attendance.holiday_id.display_name)
        attendance.holiday_id.action_refuse()


attendances.write({
    'retardo' : 0,
    'tomado_para_falta' : 0,
    'falta' : 0,
    'procesado' : 0,
    'payslip_extra_id' : False,
    'holiday_id' : False,
})
x

exit()

