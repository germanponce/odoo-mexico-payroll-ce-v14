# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import logging
_logger = logging.getLogger(__name__)
    


    
class HRPayslip_Extra(models.Model):
    _inherit = 'hr.payslip.extra'    
    
    dinning_attendance_id = fields.Many2one('hr.attendance.dinning', string="Asistencia Comedor", readonly=True)    
    
    
class HRAttendanceDinningRoom(models.Model):
    _name = 'hr.attendance.dinning'
    _description = "Asistencia a Comedor"
    _name_rec = "date"
    
    
    employee_id = fields.Many2one('hr.employee', string="Trabajador", required=True)
    date        = fields.Date(string="Fecha", default=fields.Date.context_today,
                              required=True)
    date_record = fields.Datetime(string="Fecha Entrada", default=fields.Datetime.now, required=True)
    company_id  = fields.Many2one('res.company', string="Compañía", required=True,
                                 default=lambda self: self.env.user.company_id)    
    
    comedor_monto_descuento_fijo = fields.Boolean(string="Monto Fijo",
                                                  related="company_id.comedor_monto_descuento_fijo",
                                                 )
    
    amount      = fields.Float(string="Monto", default=0, 
                               required=True, digits=(16,2))
    
    hr_extra_ids = fields.One2many('hr.payslip.extra', 'dinning_attendance_id', 
                                   string="Extras de Nómina", readonly=True)
    
    
    @api.model
    def default_get(self, default_fields):        
        res = super(HRAttendanceDinningRoom, self).default_get(default_fields)
        
        if self.env.user.company_id.comedor_monto_descuento_fijo:
            res.update({'amount' : self.env.user.company_id.comedor_monto_descuento})
        
        return res
    
    @api.constrains('employee_id', 'company_id', 'date','amount')
    def _check_no_more_than_two(self):
        self.env.cr.execute("""
                    SELECT count(attendance.id) as cuenta
                    FROM hr_attendance_dinning attendance
                    WHERE attendance.employee_id = %s AND attendance.date = %s
                    AND attendance.company_id=%s;""",
                    (self.employee_id.id, self.date.strftime('%Y-%m-%d'), self.company_id.id))
        res = self.env.cr.fetchone()
        res = res and res[0] or False
        if res and res > 2:
            raise ValidationError(_("No puede registrar Asistencia a comedor mas de 2 veces en un día..."))
            
        if not self.comedor_monto_descuento_fijo and self.amount <= 0:
            raise ValidationError(_("No puede registrar Asistencia a comedor con monto = 0"))
            

    
    @api.model
    def create(self, vals):
        # Valores por defecto
        hr_salary_rule_id = self.env['hr.salary.rule'].search([('is_dinning_attendance','=',1)], limit=1)
        if not hr_salary_rule_id:
            raise ValidationError(_('Advertencia !\nEs necesario que configure una regla Salarial tipo Deducción como "Concepto para Comedor"'))
        employee_id = self.env['hr.employee'].browse([vals['employee_id']])
        #Validaciones
        contract_id = employee_id.contract_id or False
        #contract_ids = self.env['hr.payslip'].get_contract(employee_id, vals['date'], vals['date'])
        #contract_id = contract_ids and self.env['hr.contract'].browse(contract_ids[0]) or False
        if not contract_id:
            raise ValidationError(_('Advertencia !\nEs necesario que configure un Contrato vigente para el empleado'))
        _logger.info("vals: %s" % vals)
        _logger.info("self.amount: %s" % self.amount)
        extra_data = {'date'        : vals['date'],
                      'hr_salary_rule_id' : hr_salary_rule_id.id,
                      'employee_id' : vals['employee_id'],
                      'contract_id' : contract_id.id,
                      'amount'      : self.env.user.company_id.comedor_monto_descuento if self.env.user.company_id.comedor_monto_descuento_fijo else vals.get('amount',0),
                      'qty'         : 1,
                      }
        vals['hr_extra_ids'] = [(0,0, extra_data)]
        res = super(HRAttendanceDinningRoom, self).create(vals)
        res.hr_extra_ids.action_confirm()
        res.hr_extra_ids.action_approve()
        return res
    
    
    def write(self, vals):
        raise ValidationError(_("Advertencia !\nNo es posible modificar un registro de asistencia a Comedor. \nElimine el registro incorrecto y vuelva a crear el registro con la información correcta"))
    
    
    def unlink(self):
        for rec in self:
            rec.hr_extra_ids.action_cancel()
        return super(HRAttendanceDinningRoom, self).unlink()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    
