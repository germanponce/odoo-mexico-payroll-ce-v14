# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.osv import expression
from datetime import datetime, timedelta, date
import pytz
from pytz import timezone
import xml
import codecs
from lxml import etree
from lxml.objectify import fromstring
import logging
_logger = logging.getLogger(__name__)

meses = ['dummy','Enero','Febrero','Marzo','Abril','Mayo', 'Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
dias_semana = ['Lun','Mar','Mie','Jue','Vie','Sab','Dom']

class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees',
                                    default=lambda self: self._get_employees(), required=True,
                                    domain=[('active','in',(True,False))]
                                   )
    
    @api.model
    def default_get(self, default_fields):
        res = super(HrPayslipEmployees, self).default_get(default_fields)
        record_ids =  self._context.get('active_ids',[])
        payslip_run = self.env['hr.payslip.run'].browse(record_ids)
        if payslip_run:
            res.update({'structure_id'    : payslip_run.struct_id.id})
        return res
    
    def _get_employees(self):
        record_ids =  self._context.get('active_ids',[])
        if not record_ids:
            return False
        payslip_run = self.env['hr.payslip.run'].browse(record_ids)
        company_id = self.env.user.company_id.id
        other_employee_ids = [w.employee_id.id for w in payslip_run.slip_ids]
        if not other_employee_ids:
            other_employee_ids = [0]
        self.env.cr.execute("select distinct employee_id from hr_contract "
                            "where employee_id is not null "
                            "and state ='open' "
                            "and date_start <= '%s' "
                            "and date_end is null "
                            "and company_id=%s "
                            "and employee_id not in (%s) "
                            "%s "
                            
                            "union all "
                            
                            "select distinct employee_id from hr_contract "
                            "where employee_id is not null "
                            "and state in ('open','close') "
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
    
    
    def compute_sheet(self):
        self.ensure_one()
        if not self.env.context.get('active_id'):
            from_date = fields.Date.to_date(self.env.context.get('default_date_start'))
            end_date = fields.Date.to_date(self.env.context.get('default_date_end'))
            payslip_run = self.env['hr.payslip.run'].create({
                'name': from_date.strftime('%B %Y'),
                'date_start': from_date,
                'date_end': end_date,
            })
        else:
            payslip_run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))

        if not self.employee_ids:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        payslips = self.env['hr.payslip']
        Payslip = self.env['hr.payslip']

        contracts = self.employee_ids._get_contracts(payslip_run.date_start, payslip_run.date_end, states=['open', 'close','baja'])
        contracts._generate_work_entries(payslip_run.date_start, payslip_run.date_end)
        work_entries = self.env['hr.work.entry'].search([
            ('date_start', '<=', payslip_run.date_end),
            ('date_stop', '>=', payslip_run.date_start),
            ('employee_id', 'in', self.employee_ids.ids),
        ])
        self._check_undefined_slots(work_entries, payslip_run)

        validated = work_entries.action_validate()
        #if not validated:
        #    raise UserError(_("Some work entries could not be validated."))

        default_values = Payslip.default_get(Payslip.fields_get())
        employee_ids = [] 
        for contract in contracts:
            if contract.employee_id.id in employee_ids:
                continue
            employee_ids.append(contract.employee_id.id)
            _logger.info("self.structure_id: %s - %s" % (self.structure_id.id, self.structure_id.name))
            _logger.info("contract.struct_id: %s - %s" % (contract.struct_id.id, contract.struct_id.name))
            values = dict(default_values, **{
                #'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                #'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                'tiponomina_id' : payslip_run.tiponomina_id.id,
                'date_payroll'  : payslip_run.date_payroll,
                'date'          : payslip_run.date_account or payslip_run.date_end,
                'company_id'    : contract.employee_id.company_id.id,
                'employee_id': contract.employee_id.id,
                'credit_note': payslip_run.credit_note,
                'payslip_run_id': payslip_run.id,
                'date_from': payslip_run.date_start,
                'date_to': payslip_run.date_end,
                'contract_id': contract.id,
                'struct_id': self.structure_id.id or contract.struct_id.id,
                'cfdi_timbrar' : payslip_run.cfdi_timbrar,
            })
            payslip = self.env['hr.payslip'].new(values)
            payslip._onchange_employee()
            values = payslip._convert_to_write(payslip._cache)
            payslips += Payslip.create(values)
        payslips.compute_sheet()
        payslip_run.state = 'verify'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.run',
            'views': [[False, 'form']],
            'res_id': payslip_run.id,
            'context' : {'slip_ids' : payslips.ids}
        }

    
    
class HrPayslipRun(models.Model):
    _inherit = ['hr.payslip.run', 'mail.thread']
    _name="hr.payslip.run"
        
            
    date_account    = fields.Date(string='Fecha Contable', readonly=True, index=True,
                                  help="Fecha en que se realiza la póliza de esta Lista de Nóminas",
                                  tracking=True,
                                  states={'draft': [('readonly', False)]}, copy=False)
    

    date_payroll    = fields.Date(string='Fecha de Pago', required=True, readonly=True, index=True,
                                  help="Fecha en que se realiza el pago de esta Nómina",
                                  default=fields.Date.context_today,
                                  tracking=True,
                                  states={'draft': [('readonly', False)]}, copy=False)
    
    tiponomina_id   = fields.Many2one('sat.nomina.tiponomina','Tipo Nómina', required=True,
                                      states={'draft': [('readonly', False)]}, readonly=True,
                                      tracking=True,
                                      default=lambda self: self.env['sat.nomina.tiponomina'].search([('code','=','O')], limit=1).id)
        
    state = fields.Selection(selection_add=[('cancel', 'Cancelada')])
    
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial',
                                states={'draft': [('readonly', False)]}, readonly=True,
                                tracking=True)
    
    journal_id   = fields.Many2one('account.journal','Diario Contable', store=True,
                                   related="struct_id.journal_id", readonly=True)
    
    to_cancel = fields.Boolean(string="Para Cancelar", readonly=True)
    cfdi_timbrar = fields.Boolean(string="Timbrar?", default=True, index=True)
    
    @api.onchange('date_payroll')
    def _onchange_date_payroll(self):
        self.date_account = self.date_payroll
        return
    

    def re_compute_payslips(self):
        self.slip_ids.compute_sheet()
        return True
    
    
    def confirm_payslips(self):
        if not self.slip_ids:
            raise ValidationError("Nada que procesar...")
        for payslip in self.slip_ids.filtered(lambda w: w.state=='draft'):
            payslip.action_payslip_done()
        return True
    
    ################

    def action_set_draft(self):
        self.ensure_one()
        self.write({'state':'draft'})
        return True
    
    
    def action_cancel_draft(self):
        self.ensure_one()
        if any(payslip.state=='done' for payslip in self.slip_ids):
            raise ValidationError(_("Advertencia !\nTiene por lo menos una Nómina Confirmada (Hecho) en esta Lista de Nóminas, por favor revise..."))
        self.slip_ids.filtered(lambda w: w.state in ('draft','verify')).action_payslip_cancel()
        self.slip_ids.filtered(lambda w: w.state=='done').action_cancel()
        self.write({'state':'cancel'})
        return True
    
    def action_set_verify(self):
        self.ensure_one()
        self.write({'state' : 'verify'})
        return True
    
    def action_cancel_close(self):
        self.ensure_one()
        if self.to_cancel:
            self.slip_ids.filtered(lambda w: w.state not in ('cancel','done')).action_payslip_cancel()
            self.slip_ids.filtered(lambda w: w.state=='done').action_cancel()
            self.write({'state':'cancel', 'to_cancel' : False})
        else:
            return {
                'name': _('Solicitar Cancelación'),
                'res_model': 'hr.payslip.cfdi.cancel.sat',
                'view_mode': 'form',
                'context': {
                    'active_model': 'hr.payslip.run',
                    'active_ids': self.ids,
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        return True
    
    ################
    
    
    def print_payroll_list_report(self):
        self.ensure_one()
        if not self.slip_ids:
            raise UserError(_("No existen Nóminas para la Impresión del Reporte."))
        wiz_id = self.env['hr.report_payroll_list.wizard'].create({})
        return {'type'      : 'ir.actions.act_window',
                'res_id'    : wiz_id.id,
                'view_mode' : 'form',
                'res_model' : 'hr.report_payroll_list.wizard',
                'target'    : 'new',
                'name'      : 'Imprimir Lista de Raya'}  
        return self.env.ref('l10n_mx_payroll.report_payroll_list_action').report_action(self)
    
    
    def print_hr_payslip_receipts(self):
        self.ensure_one()
        if not self.slip_ids.filtered(lambda w: w.state in ('draft','verify','done')):
            raise UserError(_("No existen Nóminas por Imprimir."))
        return self.env.ref('l10n_mx_payroll.report_hr_payslip_action').report_action(self.slip_ids.filtered(lambda w: w.state in ('draft','verify','done')))

    
    def action_view_analysis(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_payslip_analysis')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_search')
        pivot_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_pivot')
        graph_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_graph')

        result = {
            'name': _('Lista de Nómina: %s') % self.name,
            'help': action.help,
            'type': action.type,
            'views': [[search_view_id, 'search'], [pivot_view_id, 'pivot'],  [graph_view_id, 'graph']],
            'target': action.target,#'fullscreen', # 
            'context': action.context,
            'res_model': action.res_model,
        }
        Subsidio_Base = self.env['hr.salary.rule'].search([('code','=','Subsidio_Base')], limit=1)
        result['context'] =  "{'pivot_measures': ['amount'], 'pivot_row_groupby': ['employee_id'],'pivot_column_groupby': ['nomina_aplicacion','salary_rule_id'], 'search_default_nomina_aplicacion_percepciones':1, 'search_default_nomina_aplicacion_deducciones':1, 'search_default_nomina_aplicacion_otrospagos':1, 'search_default_no_suma_0':1}"
        
        result['domain'] = "[('amount','!=',0), ('payslip_run_id','=',%s)]" % (self.id)
        _logger.info("result: %s" % result)
        return result