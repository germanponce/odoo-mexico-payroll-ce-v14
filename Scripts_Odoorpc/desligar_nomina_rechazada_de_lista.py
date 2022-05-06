# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc


odoo = odoorpc.ODOO('interlogic.odoo.com', port=80)

# Login
odoo.login('mailync-interlogic-master-678474', 'israelcruz', '4rg1lC0nsult1ng')

payslip_obj = odoo.env['hr.payslip']

res = payslip_obj.search([('state','=','cancel'),
                          ('payslip_run_id','!=',False)
                         ])
cant = len(res)
payslips = payslip_obj.browse(res)
payslips.write({'payslip_run_id':False})
exit()

