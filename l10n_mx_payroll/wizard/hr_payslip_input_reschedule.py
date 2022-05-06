# -*- encoding: utf-8 -*-
#

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta

import odoo.tools as tools

import logging
_logger = logging.getLogger(__name__)


class HRPayslipInputReSchedule(models.TransientModel):
    _name = 'hr.payslip.input.reschedule'
    _description = "Wizard para Re-agendar los Extras de Nómina a Eliminar de Nomina"
    
    input_line_id = fields.Many2one('hr.payslip.input', string="Línea", 
                                    required=False)
    extra_id =  fields.Many2one('hr.payslip.extra', string="Extra de Nómina a Reagendar", 
                                    required=False)
    
    extra_employee_id = fields.Many2one('hr.employee', string="Empleado",
                                        related="extra_id.employee_id")
    
    extra_date = fields.Date(related="extra_id.date")
    
    extra_salary_rule_id   = fields.Many2one('hr.salary.rule', string='Concepto', 
                                             related="extra_id.hr_salary_rule_id")

    extra_qty = fields.Float(related="extra_id.qty")
    
    extra_amount = fields.Float(related="extra_id.amount")
    
    extra_extra_discount_id   = fields.Many2one('hr.payslip.extra.discounts', 
                                                related="extra_id.extra_discount_id")
    
    reschedule_all_extras = fields.Boolean(string="Re-programar los extras próximos", default=True)
    
    new_date = fields.Date(string="Nueva Fecha", required=True)
    

    def cancel_extra(self):
        slip = self.input_line_id.payslip_id
        self.input_line_id.payslip_extra_id.write({'state':'approved'})
        self.input_line_id.payslip_extra_id.action_reject()
        self.input_line_id.payslip_extra_id = False
        self.input_line_id.unlink()
        slip.compute_sheet()
        return True
        
        
    def update_payslip_extra(self):
        slip = self.input_line_id.payslip_id
        dias = (self.new_date - self.extra_date).days + 1
        if not dias or dias < 0:
            raise ValidationError(_("No puede re-programar a una fecha anterior a la actual"))
        
        if self.new_date <= self.input_line_id.payslip_id.date_to:
            raise ValidationError(_("No puede cambiar la fecha para que quede anterior al final del periodo de esta Nómina"))
            
        self.input_line_id.payslip_extra_id.write({'state':'approved'})
        self.input_line_id.payslip_extra_id = False
        self.input_line_id.unlink()
        
        if self.extra_extra_discount_id and self.reschedule_all_extras:
            for _extra in self.extra_extra_discount_id.payslip_extra_ids.filtered(lambda w: w.date >= self.extra_date and w.state=='approved'):
                _extra.write({'date' : _extra.date + timedelta(days=dias)})
            self.extra_extra_discount_id.message_post(subject='Re-programacion', 
                                                      body='Se re-programaron los descuentos %s dias posterior a la fecha original' % dias)
        else:
            self.extra_id.write({'date' : self.new_date})
        
        slip.compute_sheet()
        return True
                    
        
            
            
        
    