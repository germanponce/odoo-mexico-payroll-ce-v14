# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc


odoo = odoorpc.ODOO('interlogic.odoo.com', port=80)
# Login
odoo.login('mailync-interlogic-master-678474', 'israelcruz', '4rg1lC0nsult1ng')

leave_obj = odoo.env['hr.leave']

res = leave_obj.search([#('date_from','>=','2020-03-17 02:00:00'),
                        #('date_to','<=','2020-03-17 23:00:00'),
                        ('request_date_from','>=','2020-03-17'),
                        ('request_date_to','<=','2020-03-17'),
                        #('holiday_status_id.name','=','FALTAS_INJUSTIFICADAS'),
                        #('state','=','refuse'),
                        ('employee_id','=',5051),
                        ('holiday_type','=','employee')])
print("res: %s" % res)
cant = len(res)
leaves = leave_obj.browse(res)
for leave in leaves:
    print("===== Ausencia ID: %s =====\n- Rango1: %s - %s - Rango2: %s - %s - Notas: %s" % (leave.id, leave.request_date_from, leave.request_date_to, leave.date_from, leave.date_to, leave.report_note.encode('utf-8')))

exit()

