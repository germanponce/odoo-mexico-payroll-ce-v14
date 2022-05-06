# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.osv import expression
from datetime import datetime, timedelta, date
import pytz
import math
from pytz import timezone
import xml
import codecs
from lxml import etree
from lxml.objectify import fromstring
import logging
_logger = logging.getLogger(__name__)


class HRContract(models.Model):
    _inherit = 'hr.contract'
    
    contrato_anterior_aumento_masivo_id = fields.Many2one(
        'hr.contract.aumento_masivo', string="Contrato Antes del Aumento", index=True)
    contrato_nuevo_aumento_masivo_id = fields.Many2one(
        'hr.contract.aumento_masivo', string="Contrato Resultado del Aumento", index=True)
    
class HRContractSDI(models.Model):
    _inherit='hr.contract.sdi'
    
    aumento_masivo_id = fields.Many2one('hr.contract.aumento_masivo', 
                                        string="Aumento Masivo", index=True)



class HRContractAumentoMasivoWizard(models.TransientModel):
    _name = 'hr.contract.aumento_masivo.wizard'
    _description ="Asistente para Aumento de Salario Masivo"

    date = fields.Date(string="Fecha", required=True, 
                       default=fields.Date.context_today)
    
    
    type = fields.Selection([('individual', 'Nuevo Salario Individual'),
                              ('porcentaje', 'Incremento en Porcentaje'),
                              ('monto','Incremento en Monto'),
                              ('general','Nuevo Salario General'),
                            ],
                            string="Tipo de Aumento", 
                            default='porcentaje', required=True)
    
    monto = fields.Float(string="Monto", default=0, required=True,
                         digits=(16,4))
    
    tipo_salario = fields.Selection([('na', 'No Aplica'),
                                     ('0', 'Fijo'),
                                     ('1', 'Variable'),
                                     ('2', 'Mixto')], 
                                    string="Tipo de Salario",
                                    default='na', required=True)
    
    sindicalizado = fields.Selection([('all','Todos'),
                                      ('Si','Sindicalizado'),
                                      ('No','De Confianza')],
                                     string="Tipo de Empleado", default='all', required=True)
    
    
    department_ids = fields.Many2many('hr.department', 'hr_department_aumento_masivo_wiz_rel',
                                      'aumento_masivo_id', 'department_id',
                                      string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_aumento_masivo_wiz_rel',
                                      'aumento_masivo_id', 'employee_id',
                                      string="Empleados")
    
    job_ids = fields.Many2many('hr.job', 'hr_job_aumento_masivo_wiz_rel',
                               'aumento_masivo_id', 'job_id',
                               string="Puestos")
    
    struct_ids = fields.Many2many('hr.payroll.structure', 'hr_payroll_struct_aumento_masivo_wiz_rel',
                                 'aumento_masivo_id', 'struct_id',
                                 string="Estructuras Salariales")
    
    
    @api.onchange('date')
    def _onchange_date(self):
        departments, employees, jobs = [], [], []
        if not self.date:
            return
        contracts = self.env['hr.contract'].search([('date_start','<=', self.date),
                                                    ('state','in',('open','pending')),
                                                    '|',
                                                    ('date_end','=', False),
                                                    ('date_end','>=', self.date)])
        for c in contracts:
            if c.department_id.id not in departments:
                departments.append(c.department_id.id)
            if c.employee_id.id not in employees:
                employees.append(c.employee_id.id)
            if c.job_id.id not in jobs:
                jobs.append(c.job_id.id)
        
        domain = {}
        if departments:
            domain['department_ids'] = [('id','in', departments)]
        if employees:
            domain['employee_ids'] = [('id','in', employees)]
        if jobs:
            domain['job_ids'] = [('id','in', jobs)]
        return {'domain': domain}
    
    
    def create_record(self):
        data = {'date' : self.date,
                'type' : self.type,
                'monto': self.monto,
                'tipo_salario' : self.tipo_salario,
                'sindicalizado' : self.sindicalizado,
               }
        
        domain = [('state','in',('open','pending')),
                  ('date_start','<=',self.date)]
        if self.department_ids:
            data.update({'department_ids' : [(6,0, self.department_ids.ids)]})
            domain.append(('department_id','in',self.department_ids.ids))
        if self.employee_ids:
            data.update({'employee_ids' : [(6,0, self.employee_ids.ids)]})
            domain.append(('employee_id','in',self.employee_ids.ids))
        if self.job_ids:
            data.update({'job_ids' : [(6,0, self.job_ids.ids)]})
            domain.append(('job_id','in',self.job_ids.ids))
        if self.struct_ids:
            data.update({'struct_ids' : [(6,0, self.struct_ids.ids)]})
            domain.append(('struct_id','in',self.struct_ids.ids))
        if self.tipo_salario!='na':
            data.update({'tipo_salario' : self.tipo_salario})
            domain.append(('tipo_salario','=',self.tipo_salario))
        if self.sindicalizado!='all':
            data.update({'sindicalizado' : self.sindicalizado})
            domain.append(('sindicalizado','=',self.sindicalizado))
        
        
        contracts = self.env['hr.contract'].search(domain)
        if not contracts:
            raise ValidationError(_("No se encontró ningún registro que cumpla con los parámetros dados."))
        _logger.info("data: %s" % data)
        record = self.env['hr.contract.aumento_masivo'].create(data)
        
        record.action_compute()
        
        return {'type'      : 'ir.actions.act_window',
                'view_type' : 'form',
                'view_mode' : 'form',
                'res_id'    : record.id,
                'res_model' : 'hr.contract.aumento_masivo',
                }
    
    
    
class HRContractAumentoMasivo(models.Model):
    _name = 'hr.contract.aumento_masivo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description ="Aumento de salario masivo"
    
    
    company_id = fields.Many2one('res.company', string='Compañía', 
                                          default=lambda self: self.env.user.company_id)
    name = fields.Char(string="Referencia", required=True, 
                       default='/', index=True)
    date = fields.Date(string="Fecha Aplicación", required=True, index=True,
                       default=fields.Date.context_today,
                       tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    
    state = fields.Selection([('draft', 'Borrador'),
                              ('done', 'Hecho'),
                              ('cancel','Cancelado')],
                             tracking=True,
                             string="Estado", default='draft', required=True, index=True)
    
    type = fields.Selection([('individual', 'Nuevo Salario Individual'),
                              ('porcentaje', 'Incremento en Porcentaje'),
                              ('monto','Incremento en Monto'),
                              ('general','Nuevo Salario General'),
                            ],
                            string="Tipo de Aumento", tracking=True,
                            readonly=True, states={'draft': [('readonly', False)]},
                            default='porcentaje', required=True, index=True)
    
    monto = fields.Float(string="Monto", default=0, required=True,
                         digits=(16,4),tracking=True,
                         readonly=True, states={'draft': [('readonly', False)]})
    
    tipo_salario = fields.Selection([('na', 'No Aplica'),
                                     ('0', 'Fijo'),
                                     ('1', 'Variable'),
                                     ('2', 'Mixto')], 
                                    string="Tipo de Salario", tracking=True,
                                    default='na', required=True, index=True, 
                                    readonly=True, states={'draft': [('readonly', False)]})
    
    sindicalizado = fields.Selection([('all','Todos'),
                                      ('Si','Sindicalizado'),
                                      ('No','De Confianza')],
                                     string="Tipo de Empleado", default='all', required=True,
                                     readonly=True, states={'draft': [('readonly', False)]})
    
    department_ids = fields.Many2many('hr.department', 'hr_department_aumento_masivo_rel',
                                      'aumento_masivo_id', 'department_id',
                                      string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_aumento_masivo_rel',
                                      'aumento_masivo_id', 'employee_id',
                                      string="Empleados")
    
    job_ids = fields.Many2many('hr.job', 'hr_job_aumento_masivo_rel',
                               'aumento_masivo_id', 'job_id',
                               string="Puestos")
    
    struct_ids = fields.Many2many('hr.payroll.structure', 'hr_payroll_struct_aumento_masivo_rel',
                                 'aumento_masivo_id', 'struct_id',
                                 string="Estructuras Salariales")
    
    line_ids = fields.One2many('hr.contract.aumento_masivo.line', 'aumento_id',
                               readonly=True, states={'draft': [('readonly', False)]},
                               string="Líneas")
    
    notes = fields.Text(string="Observaciones",
                        readonly=True, states={'draft': [('readonly', False)]})
    
    @api.depends('line_ids')
    def _compute_lines(self):
        for rec in self:
            rec.count_lines = len(rec.line_ids.ids)
    
    count_lines = fields.Integer(string="# Líneas", compute="_compute_lines")
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('hr.contract.aumento_masivo') or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.contract.aumento_masivo') or '/'
        return super(HRContractAumentoMasivo, self).create(vals)
    
    def action_cancel(self):
        contract_sdi_ids = self.env['hr.contract.sdi'].search([('aumento_masivo_id','=', self.id)])
        if not contract_sdi_ids:
            raise ValidationError(_('Error ! No puede Cancelar este registro porque es anterior a la actualización'))
        res = contract_sdi_ids.unlink()
        contracts = self.env['hr.contract'].search([('contrato_nuevo_aumento_masivo_id','=', self.id)])
        res2 = contracts.unlink()
        contracts = self.env['hr.contract'].search([('contrato_anterior_aumento_masivo_id','=', self.id)])
        res2 = contracts.write({'date_end': False,
                                'state' : 'open',
                                'contrato_anterior_aumento_masivo_id' : False})
        return self.write({'state':'cancel'})    
    
    def action_view_lines(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_contract_aumento_masivo_line')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.hr_contract_aumento_masivo_line_search')
        tree_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.hr_contract_aumento_masivo_line_tree')
        form_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.hr_contract_aumento_masivo_line_form')

        result = {
            'name': _('Líneas de Aumento Masivo de Salario %s') % self.name,
            'help': action.help,
            'type': action.type,
            'views': [[tree_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        result['domain'] = "[('aumento_id','=',%s)]" % (self.id)
        return result
    
    
    def action_compute(self):
        self.ensure_one()
        presta_obj = self.env['sat.nomina.tabla_prestaciones']
        tabla_vac_obj = self.env['sat.nomina.tabla_vacaciones']
        
        contract_obj = self.env['hr.contract']
        holiday_obj = self.env['hr.leave']
        
        contract_ids = contract_obj.browse([]) 
        
        domain1 = [('employee_id','!=',False),
                   ('date_start','<=', self.date),
                   ('state','=','open'),
                   '|',
                   ('date_end','=', False),
                   ('date_end','>=', self.date)]
        
        domain2 = [('employee_id','!=',False),
                   ('date_start','<=', self.date),
                   ('date_end','>=', self.date),
                   ('state','=','close')]
        
        if self.department_ids:
            domain1.append(('department_id','in',self.department_ids.ids))
            domain2.append(('department_id','in',self.department_ids.ids))
        if self.struct_ids:
            domain1.append(('struct_id','in',self.struct_ids.ids))
            domain2.append(('struct_id','in',self.struct_ids.ids))
        if self.employee_ids:
            domain1.append(('employee_id','in',self.employee_ids.ids))
            domain2.append(('employee_id','in',self.employee_ids.ids))
        if self.job_ids:
            domain1.append(('job_id','in',self.job_ids.ids))
            domain2.append(('job_id','in',self.job_ids.ids))
        if self.tipo_salario!='na':
            domain1.append(('tipo_salario','=', self.tipo_salario))
            domain2.append(('tipo_salario','=', self.tipo_salario))
        if self.sindicalizado!='all':
            domain1.append(('sindicalizado','=', self.sindicalizado))
            domain2.append(('sindicalizado','=', self.sindicalizado))

        contracts1 = contract_obj.search(domain1)
        contracts2 = contract_obj.search(domain2)
        contract_ids =  contracts1 +  contracts2
        
        self.line_ids.unlink()
        lines = []
        for contract in contract_ids:
            data = {'contract_id' : contract.id }
            antig_laboral = ((self.date - contract.fecha_ingreso).days + 1.0) / 365.25
            data.update({'fecha_alta_reingreso' : contract.fecha_ingreso,
                         'antiguedad' : ((self.date - contract.fecha_ingreso).days + 1.0) / 365.25,
                         'actual_salario_diario' : contract.cfdi_sueldo_base,
                         'actual_sbc_parte_fija' : contract.cfdi_salario_diario_integrado2 or \
                                                    contract.cfdi_salario_diario_integrado,
                         
                        })
                
            holidays = holiday_obj.search([
                ('employee_id','=', contract.employee_id.id),
                ('date_from', '<=', self.date), 
                ('date_to','>=',self.date), 
                ('state','=','validate'),
            ])
            
            data.update({'incapacitado' : bool(holidays),
                         'aplicar_aumento' : not bool(holidays)})
            
            
            prestacion = presta_obj.search([('sindicalizado','=',contract.sindicalizado),
                                            ('antiguedad','=',math.ceil(antig_laboral))], limit=1)
            
            if prestacion:            
                dias_vacaciones = prestacion.dias_vacaciones
                dias_aguinaldo = prestacion.dias_aguinaldo
                porc_prima_vacacional = prestacion.prima_vacacional
            else:                
                dias_aguinaldo = 15.0
                vacaciones = tabla_vac_obj.search([
                    ('antiguedad','=', math.ceil(antig_laboral))],limit=1)
                dias_vacaciones = vacaciones and vacaciones.dias or 0
                porc_prima_vacacional = 25.0
            _logger.info("dias_vacaciones: %s" % dias_vacaciones)
            _logger.info("dias_aguinaldo: %s" % dias_aguinaldo)
            _logger.info("porc_prima_vacacional: %s" % porc_prima_vacacional)
            
            aguinaldo = contract.cfdi_sueldo_base * dias_aguinaldo
            prima_vacacional = (contract.cfdi_sueldo_base * dias_vacaciones * (porc_prima_vacacional / 100.0))
            factor_integracion = ((contract.cfdi_sueldo_base * 365.0) + aguinaldo + prima_vacacional) / (contract.cfdi_sueldo_base * 365.0)
            
            data.update({'dias_vacaciones' : dias_vacaciones,
                         'porc_prima_vacacional' : porc_prima_vacacional,
                         'dias_aguinaldo' : dias_aguinaldo,
                         'factor_integracion' : factor_integracion,
                        })
            
            
            if self.type=='porcentaje':
                nuevo_salario = contract.cfdi_sueldo_base * (1.0 + (self.monto / 100.0))
            elif self.type=='monto':
                nuevo_salario = contract.cfdi_sueldo_base + self.monto
            elif self.type=='general':
                nuevo_salario = self.monto
            elif self.type=='individual':
                nuevo_salario = 0
                
            nuevo_salario_diario_integrado = nuevo_salario * factor_integracion
            variable  = contract.cfdi_salario_diario_integrado2 - contract.cfdi_salario_diario_integrado
            data.update({
                'sal_nuevo_salario_diario' : nuevo_salario,
                'sal_nuevo_salario_diario_integrado' : nuevo_salario_diario_integrado,
                'parte_variable' : variable,
                'sal_nuevo_sbc_parte_fija' : nuevo_salario_diario_integrado + variable})
            
            lines.append((0,0,data))
    
        self.line_ids = lines
        return True
    
    
    def action_confirm(self):
        self.ensure_one()
        hr_contract_sdi_obj = self.env['hr.contract.sdi']
        date_end = self.date - timedelta(days=1)
        for line in self.line_ids.filtered(lambda w: w.aplicar_aumento):
            contract_date_end = line.contract_id.date_end
            xdate_end = line.contract_id.date_start if line.contract_id.date_start==line.date else date_end
            line.contract_id.write({'date_end' : xdate_end,
                                    'state' : 'close',
                                    'contrato_anterior_aumento_masivo_id' : self.id})
            
            if contract_date_end and contract_date_end <= date_end:
                contract_date_end = line.date
            contract = line.contract_id.copy(default={'cfdi_sueldo_base' : line.sal_nuevo_salario_diario,
                                                      'date_start'  : line.date,
                                                      'date_end' : contract_date_end,
                                                      'state' : 'open',
                                                      'contrato_anterior_aumento_masivo_id' : False,
                                                      'contrato_nuevo_aumento_masivo_id': self.id})
            r = hr_contract_sdi_obj.create({
                'contract_id' : contract.id,
                'date'        : self.date,
                'amount'      : line.sal_nuevo_sbc_parte_fija,
                'aumento_masivo_id': self.id,
                'notes'       : _('Aumento Masivo de Salario %s' % line.aumento_id.name),
            })
            #nr = r.copy(default={'contract_id' : contract.id,
            #                    'aumento_masivo_id': self.id})
            line.new_contract_id = contract.id
        return self.write({'state':'done'})
        

    
    
class HRContractAumentoMasivoLine(models.Model):
    _name = 'hr.contract.aumento_masivo.line'
    _description ="Lineas aumento masivo"
    _rec_name='contract_id'
    
    
    
    aumento_id = fields.Many2one('hr.contract.aumento_masivo', string="Aumento", index=True)
    company_id = fields.Many2one('res.company', string='Compañía', 
                                 related="aumento_id.company_id", store=True)
    date = fields.Date(related='aumento_id.date', store=True, index=True)
    state = fields.Selection(related='aumento_id.state', store=True)
    type = fields.Selection(related='aumento_id.type', store=True)    
    monto = fields.Float(related='aumento_id.monto', store=True)
    
    new_contract_id = fields.Many2one('hr.contract', string="Contrato Nuevo")
    contract_id = fields.Many2one('hr.contract', string="Contrato", required=True)
    contract_state = fields.Selection(related="contract_id.state", store=True,
                                      string="Estado Contrato")
    employee_id = fields.Many2one('hr.employee', related="contract_id.employee_id",
                                 store=True, index=True)
    
    incapacitado = fields.Boolean(string="Incap. en Fecha", default=False)
    aplicar_aumento = fields.Boolean(string="Aplicar Aumento", default=True)
    
    actual_salario_diario = fields.Float(string="Actual Salario Diario", 
                                             digits=(16,4), default=0)
    
    actual_sbc_parte_fija = fields.Float(string="Actual SBC (parte fija)", 
                                             digits=(16,4),default=0)
    
    
    fecha_alta_reingreso = fields.Date(string="Alta / Reingreso", 
                                       related="contract_id.fecha_ingreso",
                                       required=False, store=True)
    
    antiguedad = fields.Integer(string="Antig.", default=0)
    
    dias_vacaciones = fields.Integer(string="Días Vacac.", default=0)
    
    porc_prima_vacacional = fields.Float(string="% Prima Vacac.", default=25.0,
                                         digits=(16,2))
    
    dias_aguinaldo = fields.Integer(string="Días Aguin.", default=15)
    
    factor_integracion = fields.Float(string="Factor Integ.", default=0, digits=(16,8))
    
    sal_nuevo_salario_diario = fields.Float(string="Nuevo Salario Diario", digits=(16,4),
                                         default=0)
    
    sal_nuevo_salario_diario_integrado = fields.Float(
        string="Nuevo SDI", digits=(16,4), default=0)
    
    parte_variable = fields.Float(
        string="Salario Parte Variable", digits=(16,4), default=0)
    
    sal_nuevo_sbc_parte_fija = fields.Float(string="Nuevo SBC (parte fija)", digits=(16,4),)
    
    
    @api.onchange('factor_integracion','sal_nuevo_salario_diario')
    def _onchange_factor_integracion(self):
        self.sal_nuevo_salario_diario_integrado = self.factor_integracion * self.sal_nuevo_salario_diario
    
    @api.onchange('parte_variable','sal_nuevo_salario_diario_integrado')
    def _onchange_sal_nuevo_salario_diario(self):
        self.sal_nuevo_sbc_parte_fija = self.sal_nuevo_salario_diario_integrado + self.parte_variable
        
        
    
