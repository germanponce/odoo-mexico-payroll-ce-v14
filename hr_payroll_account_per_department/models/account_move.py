# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, date, timedelta
from odoo.tools import float_compare, float_is_zero
import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    payslip_id = fields.Many2one('hr.payslip', string="Nómina", index=True)
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lista de Nómina", 
                                     related='payslip_id.payslip_run_id',
                                     store=True, index=True)
    
    payslip_employee_id = fields.Many2one('hr.employee', string="Empleado (Nómina)", 
                                     related='payslip_id.employee_id',
                                     store=True, index=True)
    

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    payslip_id = fields.Many2one('hr.payslip', string="Nómina", 
                                 related="move_id.payslip_id", store=True,
                                 index=True)
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lista de Nómina", 
                                     related='payslip_id.payslip_run_id',
                                     store=True, index=True)
    
    payslip_employee_id = fields.Many2one('hr.employee', string="Empleado (Nómina)", 
                                     related='payslip_id.employee_id',
                                     store=True, index=True)