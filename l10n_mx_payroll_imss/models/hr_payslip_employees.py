# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    @api.model
    def _get_employees(self):
        record_ids =  self._context.get('active_ids',[])
        if not record_ids:
            return False
        payslip_run = self.env['hr.payslip.run'].browse(record_ids)
        company_id = self.env.user.company_id.id
        other_employee_ids = [w.employee_id.id for w in payslip_run.slip_ids]
        self.env.cr.execute("select distinct employee_id from hr_contract "
                            "where employee_id is not null "
                            "and state in ('open','pending','close') "
                            "and date_end >= '%s' and date_start <= '%s'"
                            "and company_id=%s "
                            "and id in "
                            "(select distinct line.contract_id from hr_employee_imss_line line "
                            " inner join hr_employee_imss imss on imss.id=line.imss_id and imss.state='confirm' and imss.type='02'"
                            " and imss.date between '%s' and '%s'"
                            " and imss.company_id=%s)"
                            % (payslip_run.date_start.isoformat(), payslip_run.date_end.isoformat(), company_id, 
                               payslip_run.date_start.isoformat(), payslip_run.date_end.isoformat(), company_id)
                           )
        other_employee_ids += [item['employee_id'] for item in self.env.cr.dictfetchall()]
        
        if not other_employee_ids:
            other_employee_ids = [0]
        _logger.info("other_employee_ids: %s" % other_employee_ids)
        self.env.cr.execute("select distinct employee_id from hr_contract "
                            "where employee_id is not null "
                            "and state in ('open','pending') "
                            "and date_start <= '%s' "
                            "and date_end is null "
                            "and company_id=%s "
                            "and employee_id not in (%s) "
                            "%s "
                            
                            "union all "
                            
                            "select distinct employee_id from hr_contract "
                            "where employee_id is not null "
                            "and state in ('open','pending','close') "
                            "and date_end >= '%s' and date_start <= '%s'"
                            "and company_id=%s "
                            "and employee_id not in (%s) "
                            "%s "
                            
                            % (payslip_run.date_end.isoformat(), company_id, ','.join([str(x) for x in other_employee_ids]),
                               ("and struct_id=%s" % payslip_run.struct_id.id) if payslip_run.struct_id else "",
                               payslip_run.date_start.isoformat(), payslip_run.date_end.isoformat(), company_id,
                               ','.join([str(x) for x in other_employee_ids]),
                               ("and struct_id=%s" % payslip_run.struct_id.id) if payslip_run.struct_id else "",
                              )
                           )
        employee_ids = [item['employee_id'] for item in self.env.cr.dictfetchall()]
        set_employee_ids = set(employee_ids)
        employee_ids = list(set_employee_ids)
        if self.env.user.company_id.maximo_de_nominas_a_generar_en_batch:
            employee_ids = employee_ids[:self.env.user.company_id.maximo_de_nominas_a_generar_en_batch]
        return [(6,0,employee_ids)]
    