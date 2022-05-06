# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
import math
import logging
_logger = logging.getLogger(__name__)


class HRPayslipIMSSWizard(models.TransientModel):
    _name = 'hr.payslip.imss.wizard'
    _description = "Asistente para calcular lo gravado / exento del IMSS"
    
    
    opcion = fields.Selection([('lista','Lista de Nóminas'),
                               ('nominas', 'Nóminas'),
                               ('periodo','Periodo')], 
                             string="Buscar por", default="lista")
    payslip_run_ids = fields.Many2many('hr.payslip.run', string="Lista de Nóminas",
                                      domain="[('state','!=','cancel')]")
    
    payslip_ids = fields.Many2many('hr.payslip', string="Nóminas",
                                  domain="[('state','=','done')]")
    
    date_from = fields.Date(string="Desde")
    date_to = fields.Date(string="Hasta")
    
    
    def compute_imss_rules(self, xdate=datetime.now().date(), payslip_recs=False):
        rules = self.env['hr.salary.rule'].search([('aplica_calculo_imss','=',1),('python_code_imss','!=',False)])
        if not rules:
            raise ValidationError(_("No hay reglas con cálculo de Gravado/Exento para IMSS"))
        slip_obj = self.env['hr.payslip']
        
        
        if payslip_recs:
            payslips = payslip_recs
        elif self.payslip_run_ids:
            payslips = slip_obj.browse([])
            for rec in self.payslip_run_ids:
                payslips += rec.slip_ids
        elif self.payslip_ids:
            payslips = self.payslip_ids
        elif self.date_from and self.date_to:
            payslips = slip_obj.search([('state','=','done'),
                                                      ('date_from','>=',self.date_from),
                                                      ('date_to','<=', self.date_to)])
        else:
            payslips = slip_obj.search([('state','=','done'),
                                                      ('date_to','=', xdate)])
        
        if not payslips:
            raise ValidationError(_("No se encontraron registros de nómina a procesar"))
            
        for slip in payslips:
            _logger.info("Procesando: %s - %s" % (slip.number, slip.employee_id.name))
            for line in slip.line_ids.filtered(lambda w: w.salary_rule_id.aplica_calculo_imss and w.salary_rule_id.python_code_imss):
                _logger.info("-- [%s] %s --" % (line.code, line.name))
                exec(line.salary_rule_id.python_code_imss)
                
        return True
        