#-*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError

#PARA FECHAS
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import time
import logging
_logger = logging.getLogger(__name__)
#OTROS
import re

class ReportStockRule(models.AbstractModel):
    _name = 'report.l10n_mx_payroll.report_payroll_list'
    _description = 'Payroll List Report'
    
    
    @api.model
    def _get_report_values(self, docids, data={}):
        rec_ids = data.get('active_ids', [])
        payroll_list = self.env['hr.payslip.run'].browse(rec_ids)
        #payroll_list = self.env['hr.payslip.run'].browse(docids)
        _logger.info("data: %s" % data)
        _logger.info("payroll_list: %s" % payroll_list)
        
        if not payroll_list.slip_ids.filtered(lambda x: x.state in ('draft','verify','done')):
            raise UserError(_("No existen Nóminas para la Impresión del Reporte."))
        
        # Departamentos
        if data.get('departments', False):
            departments = "and contract.department_id in (%s)" % str(data.get('departments')).replace('[','').replace(']','')
            department_ids = data.get('departments')
        else:
            departments = "and contract.department_id is not null"
            department_ids = False
        
        # Empleados
        if data.get('employees', False):
            employees = "and contract.employee_id in (%s)" % str(data.get('employees')).replace('[','').replace(']','')
            employee_ids = data.get('employees')
        else:
            employees = ""
            employee_ids = False
        _logger.info("employee_ids: %s" % employee_ids)
        
        # Puestos de Trabajo    
        if data.get('jobs', False):
            jobs = "and contract.job_id in (%s)" % str(data.get('jobs')).replace('[','').replace(']','')
            job_ids = data.get('jobs')
        else:
            jobs = ""
            job_ids = False
        _logger.info("job_ids: %s" % job_ids)
        
        # Analiticas
        if data.get('analytic_accounts', False):
            analytic_accounts = "and contract.analytic_account_id in (%s)" % str(data.get('analytic_accounts')).replace('[','').replace(']','')
            analytic_account_ids = self.env['account.analytic.account'].browse(data.get('analytic_accounts'))
        else:
            analytic_accounts = ""
            analytic_account_ids = False
        _logger.info("analytic_account_ids: %s" % job_ids)
        
        # Tipo de Empleado
        if data.get('tipo_empleado', False) != 'all':
            tipo_empleado = "and contract.sindicalizado='%s'" % data.get('tipo_empleado')
            tipo_empleados = [data.get('tipo_empleado')]
        else:
            tipo_empleado = ""
            tipo_empleados = False
        
        date_from = payroll_list.date_start.strftime('%d/%m/%Y')
        date_to = payroll_list.date_end.strftime('%d/%m/%Y')
        total_no_empleados = 0 #No. de empleados
        
        self.env.cr.execute("""
            select distinct contract.id
            from hr_payslip slip
                inner join hr_contract contract on slip.contract_id=contract.id %s %s %s %s %s
            where slip.payslip_run_id=%s and slip.state in ('draft','verify','done');
            """ % (departments, employees, jobs, 
                   tipo_empleado, analytic_accounts, payroll_list.id))
        
        contract_ids = [item['id'] for item in self.env.cr.dictfetchall()]
        if not contract_ids:
            raise ValidationError(_("No se encontraton Nóminas con los parámetros indicados."))
        #raise ValidationError('contract_ids: %s' % contract_ids)
        self.env.cr.execute("""
            select distinct contract.department_id
            from hr_payslip slip
                inner join hr_contract contract on slip.contract_id=contract.id and contract.id in (%s)
            where slip.payslip_run_id=%s and slip.state in ('draft','verify','done');
            """ % (','.join(str(_c) for _c in contract_ids), payroll_list.id))
        
        department_ids = (x[0] for x in self.env.cr.fetchall())
        if not department_ids:
            raise ValidationError(_("No se encontraton Nóminas con los parámetros indicados."))
        
        departments = self.env['hr.department'].browse(department_ids)
        conceptos_por_departamento = {}
        for department in departments:
            # Debug
            _logger.info("Procesando: [%s] %s" % (department.id, department.complete_name))
            # Fin Debug
            conceptos_por_departamento[department.id] = {
                'percepciones' : self.get_payroll_lines(
                    payroll_list=payroll_list, 
                    department=department, 
                    contracts=contract_ids,
                    tipo='percepciones'),
                'deducciones'   : self.get_payroll_lines(
                    payroll_list=payroll_list, 
                    department=department, 
                    contracts=contract_ids,
                    tipo='deducciones'),
            }
            _logger.info("\nconceptos_por_departamento[department.id]: %s" % conceptos_por_departamento[department.id])
            #raise ValidationError("Pausa")
        # Debug
        #for x in conceptos_por_departamento.keys():
        #    _logger.info("\nconceptos_por_departamento[%s]: %s" % (x, conceptos_por_departamento[x]))
        # Fin Debug
        conceptos_todos_departamentos = {
                'percepciones' : self.get_payroll_lines(
                    payroll_list=payroll_list, 
                    department=departments, 
                    contracts=contract_ids,
                    tipo='percepciones'),
                'deducciones'   : self.get_payroll_lines(
                    payroll_list=payroll_list, 
                    department=departments, 
                    contracts=contract_ids,
                    tipo='deducciones'),
            }
        
        # Debug
        #_logger.info("\nconceptos_todos_departamentos: %s" % conceptos_todos_departamentos)
        # Fin Debug
        _logger.info("contract_ids: %s" % contract_ids)
        data = {
            'docs'      : payroll_list,
            'departments' : departments,
            'contracts' : contract_ids,
            'date_from' : date_from,
            'date_to'   : date_to,
            'conceptos_por_departamento' : conceptos_por_departamento,
            'conceptos_todos_departamentos' : conceptos_todos_departamentos,
        }
        #raise ValidationError("Pausa")
        return data


    def get_payroll_lines(self, payroll_list=False, department=False, contracts=False, tipo=False):
        conceptos = self.env['hr.payslip.line'].browse()
        _logger.info("contracts: %s - tipo: %s" % (contracts, tipo))
        for nomina in payroll_list.slip_ids.filtered(lambda w: w.contract_id.id in contracts):
            if nomina.contract_id.department_id.id not in department.ids:
                _logger.info("saltando...")
                continue
            if tipo=='percepciones':
                conceptos += nomina.percepciones_ids + nomina.otrospagos_ids.filtered(lambda w: w.salary_rule_id.tipootropago_id.code!='002')
            elif tipo=='deducciones':
                conceptos += nomina.deducciones_ids + nomina.otrospagos_ids.filtered(lambda w: w.salary_rule_id.tipootropago_id.code=='002' and not w.no_suma)
        
        data ={}
        for line in conceptos:
            if line.salary_rule_id.id not in data.keys():
                data[line.salary_rule_id.id] = {'name'  : line.name,
                                                'salary_rule_id' : line.salary_rule_id,
                                                'total': (line.total * -1.0) if tipo=='deducciones' and line.salary_rule_id.tipootropago_id.code=='002' else line.total}
            else:
                data[line.salary_rule_id.id]['total'] += (line.total * -1.0) if tipo=='deducciones' and line.salary_rule_id.tipootropago_id.code=='002' else line.total
        return data
        
        
