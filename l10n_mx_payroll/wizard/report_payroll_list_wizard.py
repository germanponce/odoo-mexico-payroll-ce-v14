# -*- encoding: utf-8 -*-
#

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta

import odoo.tools as tools

import logging
_logger = logging.getLogger(__name__)


class HRReport_Payroll_ListWizard(models.TransientModel):
    _name = 'hr.report_payroll_list.wizard'
    _description = "Wizard para generar el reporte de Lista de Raya aplicando filtros"
    
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lista de Nómina",
                                    required=False)
    
    department_ids = fields.Many2many('hr.department', 'hr_department_payroll_list_rel',
                                      'wizard_id', 'department_id',
                                      string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_payroll_list_rel',
                                      'wizard_id', 'employee_id',
                                      string="Empleados")
    
    job_ids = fields.Many2many('hr.job', 'hr_job_payroll_list_rel',
                               'wizard_id', 'job_id',
                               string="Puestos de Trabajo")
    
    sindicalizado = fields.Selection([('all','Todos'),
                                      ('Si','Sindicalizado'),
                                      ('No','De Confianza')],
                                     string="Tipo de Empleado", default='all')
    
    analytic_account_ids = fields.Many2many('account.analytic.account', 
                                            'hr_analytic_payroll_list_rel',
                                            'wizard_id', 'analytic_account_id',
                                            string="Analíticas")
        
    @api.model
    def default_get(self, fields):
        rec = super(HRReport_Payroll_ListWizard, self).default_get(fields)
        active_id = self._context.get('active_id')
        active_model = self._context.get('active_model')
        
        if not active_id or active_model != 'hr.payslip.run':
            return rec
        rec.update({'payslip_run_id' : active_id})
        return rec

        
    
    @api.onchange('payslip_run_id')
    def _onchange_payslip_run_id(self):
        departments, employees, jobs, analytic_accounts = [], [], [], []
        if not self.payslip_run_id:
            return
        for slip in self.payslip_run_id.slip_ids.filtered(lambda w: w.state!='cancel'):
            if slip.contract_id.department_id.id not in departments:
                departments.append(slip.contract_id.department_id.id)
            if slip.employee_id.id not in employees:
                employees.append(slip.employee_id.id)
            if slip.contract_id.job_id.id not in jobs:
                jobs.append(slip.contract_id.job_id.id)
            if slip.contract_id.analytic_account_id.id not in analytic_accounts:
                analytic_accounts.append(slip.contract_id.analytic_account_id.id)
        
        domain = {}
        if departments:
            domain['department_ids'] = [('id','in', departments)]
        if employees:
            domain['employee_ids'] = [('id','in', employees)]
        if jobs:
            domain['job_ids'] = [('id','in', jobs)]
        if analytic_accounts:
            domain['analytic_account_ids'] = [('id','in', analytic_accounts)]
        return {'domain': domain}
    
    
    def get_report(self):
        rec_ids = self._context.get('active_ids', [])
        payroll_list = self.env['hr.payslip.run'].browse(rec_ids)
        data = self._context.copy()
        #data.update({'payslip_run_ids' : payroll_list.ids})
        
        if self.department_ids:
            data.update({'departments' : self.department_ids.ids})
        if self.employee_ids:
            data.update({'employees' : self.employee_ids.ids})
        if self.job_ids:
            data.update({'jobs' : self.job_ids.ids})
        if self.analytic_account_ids:
            data.update({'analytic_accounts' : self.analytic_account_ids.ids})
        data.update({'tipo_empleado' : self.sindicalizado})
        _logger.info("\n\ndata: %s\n" % data)
        #raise ValidationError("Pausa 123")
        return self.env.ref('l10n_mx_payroll.report_payroll_list_action').report_action(payroll_list, data=data) # payroll_list
        
        