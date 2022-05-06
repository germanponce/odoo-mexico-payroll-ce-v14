# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc


odoo = odoorpc.ODOO('interlogic.odoo.com', port=80)

# Login
odoo.login('mailync-interlogic-master-678474', 'israelcruz', '4rg1lC0nsult1ng')

extra_obj = odoo.env['hr.payslip.extra']

res = extra_obj.search([('state','=','done'),
                        ('payslip_id','=',False)])


cant = len(res)
extras = extra_obj.browse(res)
extras.write({'state':'approved'})

exit()

