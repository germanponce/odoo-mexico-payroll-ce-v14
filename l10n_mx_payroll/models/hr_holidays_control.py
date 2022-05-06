# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import logging
_logger = logging.getLogger(__name__)

class HRContract_SDI_Wizard(models.TransientModel):
    _name = 'hr.leaves.wizard'
    _description = "Wizard para crear Vacaciones a disfrutar por empleado"
    
    date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    
    department_ids = fields.Many2many('hr.department', string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', string="Empleados")
    
    
    
    def get_vacations(self):
        return self.env['hr.leave.allocation'].\
                    get_vacations(xdate=self.date, 
                                  #contract_type_ids=self.contract_type_ids,
                                  department_ids=self.department_ids,
                                  employee_ids=self.employee_ids)

        
