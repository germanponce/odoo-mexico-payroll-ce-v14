# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import time
import math
from dateutil import relativedelta
import logging
_logger = logging.getLogger(__name__)


class hr_settlement_batch_wizard(models.TransientModel):
    _name = "hr.settlement.batch.wizard"
    _description = "Confirm the selected invoices"
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_settlement_batch_rel', 
                                    'settlement_batch_id', 'employee_id', 'Empleados')
    
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', 
                                required=True,
                                help='Seleccione la Estructura Salarial a utilizar')
    
    hr_causa_id = fields.Many2one('hr.causa_fin_relacion_laboral', required=True, 
                                  string="Causa de Terminación")

    type        = fields.Selection([('finiquito','Finiquito'),
                                    ('liquidacion','Liquidación')],
                                   string="Tipo", required=True)
    contract_date_end = fields.Date(string="Fecha Fin Contrato", required=True,
                                   default=fields.Date.context_today,
                                   help="Fecha Final del Contrato a aplicarla a los Empleados seleccionados")
    
    @api.onchange('hr_causa_id')
    def _onchange_type(self):
        self.type = self.hr_causa_id.type
        
        
    
    def compute_sheet(self):
        settlement_obj = self.env['hr.settlement']
        settlements = self.env['hr.settlement']
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.settlement.batch'].browse(active_id).\
                                read(['date', 'date_payroll', 'date_from', 'date_to', 'journal_id',
                                     'type','hr_causa_id'])
        if not self.employee_ids:
            raise UserError(_("Debe seleccionar por lo menos un Empleado para generar Finiquito."))
        for employee in self.employee_ids:
            data = {
                'employee_id'   : employee.id,
                'date'          : run_data.get('date'),
                'date_from'     : run_data.get('date_from'),
                'date_to'       : run_data.get('date_to'),
                'date_payroll'  : run_data.get('date_payroll'),
                'journal_id'    : run_data.get('journal_id'),
                'type'          : self.type,
                'hr_causa_id'   : self.hr_causa_id.id,
                'company_id'    : employee.company_id.id,
                'settlement_batch_id' : active_id,
                'struct_id'     : self.struct_id.id,
            }
            _settlement = settlement_obj.new(data)
            _settlement._onchange_employee_id()            
            settlement_data = _settlement._convert_to_write(_settlement._cache)
            settlement_data['contract_date_end'] = self.contract_date_end
            settlement = settlement_obj.create(settlement_data)
            settlement.compute_data()
            settlements += settlement
        return {'type': 'ir.actions.act_window_close'}
    
    

class hr_settlement_batch(models.Model):
    _name="hr.settlement.batch"
    _inherit = ['mail.thread']
    _description="Varias Liquidaciones / Finiquitos a la vez"
    _order = 'date, name'
    
    
    
    @api.depends('state', 'settlement_ids')
    def _compute_settlement_count(self):
        for rec in self:
            rec.settlement_count = len(set(rec.settlement_ids.ids))

    
    
    name = fields.Char(string="Referencia", required=True, index=True, 
                       tracking=True)
    
    date    = fields.Date(string='Fecha Baja', required=True, 
                          default=fields.Date.context_today, index=True, 
                          readonly=True, states={'draft': [('readonly', False)]}, 
                          tracking=True)
    
    state   = fields.Selection([('draft','Borrador'),
                                ('done', 'Hecho'),
                                ('cancel', 'Cancelado')],
                               string='Estado', default='draft', 
                               index=True, tracking=True)
    
    notes = fields.Text(string="Observaciones",
                        readonly=True, states={'draft': [('readonly', False)]})
            
    date_from = fields.Date(string="Fecha Inicial", required=True, 
                            index=True, readonly=True, 
                            default=time.strftime('%Y-%m-01'),
                            states={'draft': [('readonly', False)]}, tracking=True)
    
    date_to   = fields.Date(string="Fecha Final", required=True, 
                            index=True, readonly=True, 
                            states={'draft': [('readonly', False)]}, tracking=True,
                            default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])
    
    date_payroll = fields.Date(string='Fecha de Pago', required=True, readonly=True, index=True,
                               help="Fecha en que se realiza el pago de esta Nómina",
                               default=fields.Date.context_today,
                               states={'draft': [('readonly', False)]}, copy=False)
    
    date_payroll_settlement = fields.Date(string='Fecha de Pago Finiquito', required=True, readonly=True, index=True,
                               help="Fecha en que se realiza el pago del Finiquito",
                               default=fields.Date.context_today,
                               states={'draft': [('readonly', False)]}, copy=False)
    
    journal_id = fields.Many2one('account.journal', 'Diario Contable', required=True,
                                 readonly=True, states={'draft': [('readonly', False)]}, 
                                 default=lambda self: self.env['account.journal'].search([('type', '=', 'general')], limit=1))
    
    
    settlement_ids = fields.One2many('hr.settlement', 'settlement_batch_id',
                                     string="Finiquitos",
                                     readonly=True, states={'draft': [('readonly', False)]}
                                    )
    
    company_id          = fields.Many2one('res.company', string='Compañía', 
                                          readonly=True, states={'draft': [('readonly', False)]},
                                          default=lambda self: self.env.company)
    
    settlement_count       = fields.Integer(string='# Finiquitos', compute='_compute_settlement_count', 
                                            store=False)
    
    @api.constrains('date_from', 'date_to', 'date')
    def _check_dates(self):
        if any(self.filtered(lambda sett_batch: sett_batch.date_from > sett_batch.date_to)):
            raise ValidationError(_("La Fecha Final no puede ser menor a la Fecha Inicial."))
        if any(self.filtered(lambda sett_batch: not (sett_batch.date_from <= sett_batch.date <= sett_batch.date_to))):
            raise ValidationError(_("La Fecha del registro debe estar entre la Fecha Inicial y Final."))
            
    _sql_constraints = [
        ('name_company_id_unique', 'unique(name,company_id)','La Referencia debe ser única por Compañía')]
    
    
    
    def action_done(self):
        for rec in self.settlement_ids.filtered(lambda x: x.state=='draft'):
            rec.action_confirm()
        for rec in self.settlement_ids.filtered(lambda x: x.state=='confirmed'):
            rec.action_done()
            contratos1 = contract_obj.search([('employee_id','=',rec.employee_id.id),
                                             ('state','=','close')])
            contratos1.write({'active':False})
            contratos2 = contract_obj.search([('employee_id','=',rec.employee_id.id),
                                             ('state','=','draft')])
            contratos2.write({'state':'cancel', 'active':False})
            rec.employee_id.write({'active':False})
            rec.contract_id.write({'state':'baja', 'active':False})
        self.write({'state': 'done'})
            
    
    def action_cancel(self):
        self.settlement_ids.filtered(lambda x: x.state in ('draft','confirmed')).action_cancel()
        self.write({'state': 'cancel'})
            
    
    
    def action_view_settlements(self):
        record_ids = self.mapped('settlement_ids')
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_settlement')
        list_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.hr_settlement_tree')
        form_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.hr_settlement_form')

        result = {
            'name': 'Finiquito(s)',
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(record_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % record_ids.ids
        elif len(record_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = record_ids.ids[0]
            
        result['context'] = "{'default_settlement_batch_id': %s, 'default_date' : '%s', 'default_date_from' : '%s', 'default_date_to' : '%s', 'default_date_payroll' : '%s', 'search_default_settlement_batch_id': [%s]}" % \
                            (self.id, self.date, self.date_from, self.date_to, self.date_payroll, self.id)
        return result  
    

class hr_settlement(models.Model):
    _name="hr.settlement"
    _inherit = ['mail.thread']
    _description="Finiquitos"
    
    
    
    @api.depends('contract_id.date_start','date')
    def _compute_data(self):
        param_fecha_inicio = self.company_id.antiguedad_finiquito
        for rec in self:
            if rec.date and rec.contract_id.date_start and rec.contract_id.fecha_ingreso:
                if param_fecha_inicio == '1': # Tomar Fecha de Inicio de Contrato
                    dias = (rec.date - rec.contract_id.date_start).days + 1
                else: # Tomar Fecha de Ingreso
                    dias = (rec.date - rec.contract_id.fecha_ingreso).days + 1
                anios= dias / 365.0
                rec.update({'antig_dias'            : dias,
                            'antig_anios'           : anios,
                            })
            else:
                rec.update({'antig_dias'            : 0,
                            'antig_anios'           : 0,
                            })

            
    settlement_batch_id = fields.Many2one('hr.settlement.batch', string='Lista de Finiquitos', 
                                          ondelete="cascade", index=True, auto_join=True)
                                     
    name    = fields.Char(string="Referencia", required=True, readonly=True, index=True, default='/')
    
    date    = fields.Date(string='Fecha Baja', required=True, default=fields.Date.context_today, index=True, 
                          readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    
    
    state   = fields.Selection([('draft','Borrador'),
                                ('confirmed', 'Confirmado'),
                                ('done', 'Hecho'),
                                ('cancel', 'Cancelado')],
                               string='Estado', default='draft', 
                               index=True, tracking=True)
    
    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, readonly=True,
                                  states={'draft': [('readonly', False)]}, index=True, 
                                  tracking=True)
    
    contract_id = fields.Many2one('hr.contract', string='Contrato', required=True, 
                                          readonly=True, states={'draft': [('readonly', False)]},
                                          tracking=True)
    
    contract_date_start = fields.Date(string='Inicio de Contrato', 
                                      readonly=True, related='contract_id.date_start')
    
    contract_date_end = fields.Date(string='Fin de Contrato', required=True, 
                                   readonly=True, states={'draft': [('readonly', False)]},
                                   tracking=True)
    
    department_id= fields.Many2one('hr.department', related="contract_id.department_id", 
                                   string="Departamento",
                                    readonly=True, store=True)
    
    type        = fields.Selection([('finiquito','Finiquito'),
                                    ('liquidacion','Liquidación')],
                                  string="Tipo", required=True, index=True,
                                  readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    
    hr_causa_id = fields.Many2one('hr.causa_fin_relacion_laboral', required=True, string="Causa de Terminación",
                                  readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    
    notes = fields.Text(string="Observaciones",
                        readonly=True, states={'draft': [('readonly', False)]})
    
    
    fecha_ingreso = fields.Date(string="Fecha Ingreso", related="contract_id.fecha_ingreso", 
                                readonly=True)
    
    cfdi_sueldo_base = fields.Float('·Sueldo Base', digits=(18,4), related="contract_id.cfdi_sueldo_base")
    
    antig_dias  = fields.Integer(string="Antigüedad Días", compute="_compute_data")
    
    antig_anios = fields.Float(string="Antigüedad Años", digits=(16,4),
                               compute="_compute_data")
    
    payslip_id = fields.Many2one('hr.payslip', string="Nómina", readonly=True, index=True)
    
    settlement_payslip_id = fields.Many2one('hr.payslip', string="Nómina del Finiquito", readonly=True, index=True)
    
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial Regular', required=True,
                                states={'draft': [('readonly', False)]}, readonly=True,
                                help='Seleccione la Estructura Salarial regular del Trabajador')
    
    settlement_struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial Finiquito', required=True,
                                states={'draft': [('readonly', False)]}, readonly=True,
                                help='Seleccione la Estructura Salarial correspondiente a Finiquitos y/o Liquidaciones')
    
    date_from = fields.Date(string="Fecha Inicial", required=True, 
                            default=fields.Date.context_today, index=True, 
                            readonly=True, 
                            states={'draft': [('readonly', False)]}, tracking=True)
    
    date_to   = fields.Date(string="Fecha Final", required=True, 
                            default=fields.Date.context_today, index=True, 
                            readonly=True, 
                            states={'draft': [('readonly', False)]}, tracking=True)
    
    date_payroll = fields.Date(string='Fecha de Pago', required=True, readonly=True, index=True,
                               help="Fecha en que se realiza el pago de esta Nómina",
                               default=fields.Date.context_today,
                               states={'draft': [('readonly', False)]}, copy=False)
    
    date_payroll_settlement = fields.Date(string='Fecha de Pago Finiquito', required=True, readonly=True, index=True,
                               help="Fecha en que se realiza el pago del Finiquito",
                               default=fields.Date.context_today,
                               states={'draft': [('readonly', False)]}, copy=False)
    
    journal_id = fields.Many2one('account.journal', 'Diario Contable', required=True,
                                 readonly=True, states={'draft': [('readonly', False)]}, 
                                 default=lambda self: self.env['account.journal'].search([('type', '=', 'general')], limit=1))
    
    ######
    calculado = fields.Boolean(string="Calculado", default=False)
    dias_trabajados = fields.Integer(string="Días Trabajados del Año actual", default=0,
                                    readonly=True, states={'draft': [('readonly', False)]})
    
    monto_indemnizacion_90_dias = fields.Float(string="Indemnización (90 días)",
                                               help="Indemnización por Despido Injustificado (ART: 48 LFT)",
                                               digits=(18,2), default=0,
                                               readonly=True, states={'draft': [('readonly', False)]})
    
    monto_indemnizacion_20_dias = fields.Float(string="Indemnización (20 días x año)", 
                                               help="Indemnización por negativa de Reinstalación (ART: 50 FRACC. II LFT)",
                                               digits=(18,2), default=0,
                                               readonly=True, states={'draft': [('readonly', False)]})
    
    suma_indemnizacion = fields.Float(string="Suma Indemnización", digits=(18,2), 
                                             compute="_get_monto_finiquito")
    
    monto_prima_antiguedad_12_dias = fields.Float(string="Prima de Antigüedad (12 días x año)", 
                                                  help="Prima de Antigüedad de trabajadores de planta (ART: 162 LFT), "
                                                       "Se considerará como salario máximo el doble del salario mínimo.",
                                                  digits=(18,2), default=0,
                                                  readonly=True, states={'draft': [('readonly', False)]})
    
    monto_prima_antiguedad_15_anios = fields.Float(string="Prima de Antigüedad (Antigüedad >= 15 años)", 
                                                   help="Prima de Antigüedad que solo aplica cuando el Trabajador tiene mas de 15 o más años de Antigüedad",
                                                   digits=(18,2), default=0,
                                                   readonly=True, states={'draft': [('readonly', False)]})
    
    suma_prima_antiguedad = fields.Float(string="Suma Prima de Antigüedad", digits=(18,2), 
                                         compute="_get_monto_finiquito")
    
    dias_aguinaldo = fields.Integer(string="Días Aguinaldo (Base)", default=15,
                                    readonly=True, states={'draft': [('readonly', False)]})
    
    proporcional_aguinaldo_dias = fields.Float(string="Proporcional Aguinaldo (Días)", digits=(18,6),
                                               default=0,
                                               readonly=True, states={'draft': [('readonly', False)]})
    
    proporcional_aguinaldo = fields.Float(string="Proporcional Aguinaldo", digits=(18,2),
                                          default=0,
                                          readonly=True, states={'draft': [('readonly', False)]})
    
    dias_vacaciones_pendientes = fields.Integer(string="Días Vacaciones Pendientes", default=0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    
    proporcional_vacaciones_dias = fields.Float(string="Proporcional Vacaciones (Días)", digits=(18,4),
                                                default=0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    proporcional_prima_vac_dias = fields.Float(string="Proporcional Prima Vac. (Días)", digits=(18,4),
                                                default=0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    
    total_dias_vacaciones = fields.Float(string="Total Días Vacaciones", digits=(18,4), 
                                         compute="_get_monto_finiquito")
    
    proporcional_vacaciones = fields.Float(string="Proporcional Vacaciones", digits=(18,2),
                                                default=0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    
    proporcional_prima_vacacional_base = fields.Float(string="% Prima Vacacional", digits=(18,2),
                                                default=25.0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    
    proporcional_prima_vacacional = fields.Float(string="Proporcional Prima Vacacional", digits=(18,2),
                                                default=0,
                                                readonly=True, states={'draft': [('readonly', False)]})
    
    monto_finiquito = fields.Float(string="Monto Finiquito", digits=(18,2), compute="_get_monto_finiquito")
    sumas           = fields.Float(string="Suma", digits=(18,2), compute="_get_monto_finiquito")
    sumas_neto      = fields.Float(string="Suma Neto", digits=(18,2), compute="_get_monto_finiquito")
    suma_isr        = fields.Float(string="Suma ISR", digits=(18,2), compute="_get_monto_finiquito")
    param_prevision_social = fields.Char(string="Cálculo Previsión Social",
                                        default='%s')
    sueldo_base_con_prevision_social = fields.Float(string="Sueldo Base con Previsión Social", digits=(18,2), 
                                                    compute="_get_monto_finiquito")
    ######
    hr_payslip_extra_ids = fields.One2many('hr.payslip.extra', 'settlement_id', 
                                           domain=[('state','!=','cancel')],
                                           string='Extras de Nómina', readonly=True)
    
    other_income_ids = fields.One2many('hr.settlement.other_income', 'settlement_id', 
                                       string='Otras Percepciones', 
                                       readonly=True, states={'draft': [('readonly', False)]})
    
    discount_ids = fields.One2many('hr.settlement.discounts', 'settlement_id', 
                                   string='Otras Deducciones', 
                                   readonly=True, states={'draft': [('readonly', False)]})
    
    percepciones_ids = fields.One2many('hr.payslip.line', 'settlement_id', 
                                       string='Percepciones', readonly=True,
                                       domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                               ('total','!=',0)])
    
    percepciones_regulares_ids = fields.One2many('hr.payslip.line', 'settlement_id', 
                                                 string='Percepciones Regulares', readonly=True,
                                                 domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                                         ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                                         ('total','!=',0),
                                                         ('no_suma', '=', False)])
    
    percepciones_no_suma_ids = fields.One2many('hr.payslip.line', 'settlement_id', 
                                               string='Percepciones en Especie', readonly=True,
                                               domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                                       ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                                       ('total','!=',0),
                                                       ('no_suma', '=', True)])
    
    deducciones_ids = fields.One2many('hr.payslip.line', 'settlement_id', string='Deducciones', readonly=True,
                                      domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                              ('salary_rule_id.nomina_aplicacion', '=', 'deduccion'),
                                              ('total','!=',0)])
    
    otrospagos_regulares_ids = fields.One2many('hr.payslip.line', 'settlement_id', 
                                               string='Otros Pagos (Regulares)', readonly=True,
                                               domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                                       ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                                       ('total','!=',0),
                                                       ('no_suma', '=', False)])
    
    otrospagos_no_suma_ids = fields.One2many('hr.payslip.line', 'settlement_id', 
                                             string='Otros Pagos (No suman)', readonly=True,
                                             domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                                     ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                                     ('total','!=',0),
                                                     ('no_suma', '=', True)])
    
    otrospagos_ids = fields.One2many('hr.payslip.line', 'settlement_id', string='Otros Pagos', readonly=True,
                                     domain=[('appears_on_payslip','=',True), ('state','!=','cancel'),
                                             ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                             ('total','!=',0)])
    
    line_ids = fields.One2many('hr.payslip.line', 'settlement_id', string='Líneas de Nómina', 
                               domain=[('state','!=','cancel')],
                               readonly=True, states={'draft': [('readonly', False)]})
    
    _sql_constraints = [
        ('name_company_unique', 'unique(name,company_id)','El registro debe ser único'),
    ]
    
    @api.depends('param_prevision_social','contract_id.cfdi_sueldo_base',
                 'dias_vacaciones_pendientes', 'proporcional_vacaciones_dias',
                 'monto_indemnizacion_90_dias', 'monto_indemnizacion_20_dias',
                 'monto_prima_antiguedad_12_dias', 'monto_prima_antiguedad_15_anios',
                 'proporcional_aguinaldo', 'proporcional_vacaciones', 'proporcional_prima_vacacional')
    def _get_monto_finiquito(self):
        for rec in self:
            rec.sueldo_base_con_prevision_social = eval(rec.param_prevision_social % rec.contract_id.cfdi_sueldo_base)
            rec.total_dias_vacaciones = rec.dias_vacaciones_pendientes + rec.proporcional_vacaciones_dias
            rec.suma_indemnizacion = rec.monto_indemnizacion_90_dias + rec.monto_indemnizacion_20_dias
            rec.suma_prima_antiguedad = rec.monto_prima_antiguedad_12_dias + rec.monto_prima_antiguedad_15_anios
            rec.sumas = rec.suma_indemnizacion + rec.suma_prima_antiguedad+\
                        rec.proporcional_aguinaldo + rec.proporcional_vacaciones +\
                        rec.proporcional_prima_vacacional
            rec.sumas_neto = rec.payslip_id.neto_a_pagar + (rec.settlement_payslip_id and rec.settlement_payslip_id.neto_a_pagar or 0.0)
            rec.suma_isr = sum(rec.payslip_id.line_ids.filtered(lambda w: w.salary_rule_id.nomina_aplicacion=='deduccion' and w.salary_rule_id.appears_on_payslip and w.salary_rule_id.tipodeduccion_id.code=='002').mapped('total')) + (rec.settlement_payslip_id and sum(rec.settlement_payslip_id.line_ids.filtered(lambda w: w.salary_rule_id.nomina_aplicacion=='deduccion' and w.salary_rule_id.appears_on_payslip and w.salary_rule_id.tipodeduccion_id.code=='002').mapped('total')) or 0.0)
            rec.monto_finiquito = rec.proporcional_aguinaldo +\
                                  rec.proporcional_vacaciones +\
                                  rec.proporcional_prima_vacacional
                        
    
    @api.depends('line_ids', 'line_ids.amount')
    def _get_payroll_resume(self):
        for payslip in self:
            percepciones_gravadas, percepciones_exentas, percepciones = 0.0, 0.0, 0.0
            percepciones_regulares, percepciones_no_suma, deducciones = 0.0, 0.0, 0.0
            otrospagos_regulares, otrospagos_no_suma, otrospagos, otrospagos_xml = 0.0, 0.0, 0.0, 0.0
            retenciones = 0.0
            for line in payslip.line_ids.filtered(lambda x: x.salary_rule_id.appears_on_payslip):
                percepciones_gravadas += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                       line.salary_rule_id.tipo_gravable == 'gravable' else 0.0
                percepciones_exentas += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                      line.salary_rule_id.tipo_gravable == 'exento' else 0.0
                    
                percepciones+= line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' else 0.0
                percepciones_regulares += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                        not line.salary_rule_id.no_suma else 0.0
                percepciones_no_suma += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                         line.salary_rule_id.no_suma else 0.0
                deducciones += line.total if line.salary_rule_id.nomina_aplicacion == 'deduccion' else 0.0
                retenciones += line.total if line.salary_rule_id.nomina_aplicacion == 'deduccion' and \
                                             line.salary_rule_id.tipodeduccion_id.code =='002' else 0.0
                
                otrospagos_regulares += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' and not line.salary_rule_id.no_suma else 0.0
                otrospagos_no_suma += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' and line.salary_rule_id.no_suma else 0.0
                otrospagos  += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' else 0.0
                if line.salary_rule_id.nomina_aplicacion == 'otrospagos':
                    if line.salary_rule_id.es_subsidio_causado and line.total:
                        otrospagos_xml  += 0.01 if not any(x.salary_rule_id.tipootropago_id.code in ('007','008') for x in payslip.otrospagos_ids) else 0.0
                    elif not line.salary_rule_id.es_subsidio_causado and \
                        line.salary_rule_id.tipootropago_id.code!='002':
                        otrospagos_xml  += line.total
                
                
            payslip.update({'sum_percepciones_gravadas' : percepciones_gravadas,
                            'sum_percepciones_exentas'  : percepciones_exentas,
                            'sum_percepciones_regulares': percepciones_regulares,
                            'sum_percepciones_no_suma' : percepciones_no_suma,
                            'sum_deducciones'   : deducciones,
                            'sum_otrospagos_regulares' : otrospagos_regulares,
                            'sum_otrospagos_no_suma'   : otrospagos_no_suma,
                            'sum_otrospagos'    : otrospagos,
                            'sum_otrospagos_xml' : otrospagos_xml,
                            'total_percepciones': percepciones + otrospagos_regulares,
                            'total_retenciones': retenciones,
                            'neto_a_pagar'  : percepciones_regulares - deducciones + otrospagos_regulares, 
                            })
        
    
    total_retenciones= fields.Float(string="Total Retenciones", digits=(18,2), 
                                    compute="_get_payroll_resume", store=True)
    total_percepciones= fields.Float(string="Total Percepciones", digits=(18,2), 
                                     compute="_get_payroll_resume", store=True)
    sum_percepciones_regulares = fields.Float(string="Subtotal Percepciones Regulares (+)", 
                                              digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones_no_suma = fields.Float(string="Subtotal Percepciones en Especie (+)", 
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones= fields.Float(string="Suma Percepciones (+)", digits=(18,2), 
                                   compute="_get_payroll_resume", store=True)
    sum_percepciones_gravadas= fields.Float(string="Percepciones Gravadas", 
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones_exentas = fields.Float(string="Percepciones Exentas", 
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_deducciones = fields.Float(string="Total Deducciones (-)",  digits=(18,2), 
                                   compute="_get_payroll_resume", store=True)
    sum_otrospagos_regulares = fields.Float(string="Subtotal Otros Pagos Regulares (+)", 
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_otrospagos_no_suma = fields.Float(string="Subtotal Otros Pagos (No Suma) (+)", 
                                          digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_otrospagos  = fields.Float(string="Total Otros Pagos (+)", digits=(18,2), 
                                   compute="_get_payroll_resume", store=True)
    sum_otrospagos_xml  = fields.Float(string="Total Otros XML", digits=(18,2), 
                                       compute="_get_payroll_resume", store=True)
    neto_a_pagar    = fields.Float(string="Neto a Pagar",  digits=(18,2), 
                                   compute="_get_payroll_resume", store=True)
    
    move_id = fields.Many2one('account.move', 'Póliza Contable', 
                              related="payslip_id.move_id", readonly=True)
    settlement_move_id = fields.Many2one('account.move', 'Póliza Finiquito', 
                              related="settlement_payslip_id.move_id", readonly=True)
    
    company_id = fields.Many2one('res.company', string='Compañía', 
                                 readonly=True, states={'draft': [('readonly', False)]}, 
                                 default=lambda self: self.env.company)
    
    @api.constrains('date_from', 'date_to', 'date')
    def _check_dates(self):
        if any(self.filtered(lambda sett_batch: sett_batch.date_from > sett_batch.date_to)):
            raise ValidationError(_("La Fecha Final no puede ser menor a la Fecha Inicial."))
        #if any(self.filtered(lambda sett_batch: not (sett_batch.date_from <= sett_batch.date <= sett_batch.date_to))):
        #    raise ValidationError(_("La Fecha de Baja debe estar entre la Fecha Inicial y Final del periodo de Nómina."))
    
    
    @api.onchange('date')
    def _onchange_date(self):
        self.contract_date_end = self.date
    
    @api.onchange('hr_causa_id')
    def _onchange_type(self):
        self.type = self.hr_causa_id.type
    
                                     
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id:
            self.contract_id = False
        else:
            contract = self.env['hr.contract'].search([('employee_id','=',self.employee_id.id),
                                                       ('state','in',('open','close','baja'))],
                                                      limit=1, order='date_start desc')
            if contract:
                self.contract_id = contract.id
                self.contract_date_end = self.date or contract.date_end
                self.param_prevision_social = self.contract_id.calculo_prevision_social
                self.struct_id = self.contract_id.struct_id.id
                dias_aguinaldo = 15
                antig = math.ceil(self.antig_anios)
                prest_line = self.env['sat.nomina.tabla_prestaciones'].search([('antiguedad','=',antig),
                                                                               ('sindicalizado','=',contract.sindicalizado)], limit=1)
                self.dias_aguinaldo = prest_line and prest_line.dias_aguinaldo or 15
        
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('hr.settlement') or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.settlement') or '/'
        if vals.get('contract_date_end', False): 
            res = super(hr_settlement, self).create(vals)
            res.contract_id.date_end = vals.get('contract_date_end', False)
            return res

        return super(hr_settlement, self).create(vals)
    
    
    
    def write(self, values):
        if 'employee_id' in values:
            raise UserError(_("Advertencia!\nNo puede cambiar el Empleado, cancele y cree otro documento"))
        if values.get('contract_date_end', False): 
            res = super(hr_settlement, self).write(values)
            for rec in self:
                rec.contract_id.date_end = values.get('contract_date_end', False)
            return res

        return super(hr_settlement, self).write(values)
    
    
    def create_extras(self, recordset):
        extra_obj = self.env['hr.payslip.extra']
        for rec in recordset:
            data = {'settlement_id'     : self.id,
                    'employee_id'       : self.employee_id.id,
                    'hr_salary_rule_id' : rec.hr_salary_rule_id.id,
                    'date'              : self.date,                    
                   }
            extra = extra_obj.new(data)
            extra.onchange_employee()
            extra_data = extra._convert_to_write(extra._cache)
            extra_data['amount'] = rec.amount
            if not extra_data.get('contract_id', False):
                raise ValidationError(_("Advertencia!\nEl Empleado no tiene Contrato válido para la fecha del Documento..."))
            rec = extra_obj.create(extra_data)
            rec.action_confirm()
            rec.action_approve()
      
    
    def compute_data(self):
        salario_minimo = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smg')],order='vigencia desc', limit=1) # ToDo => Revisar si el trabajador es Frontera Norte
        salario_minimo_frontera_norte = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smfn')],order='vigencia desc', limit=1)
        param = self.company_id.antiguedad_segun_lft
        antig_anios = round(self.antig_anios) if param == '1' else self.antig_anios - (self.antig_anios % 1)
        # monto_indemnizacion_90_dias
        self.monto_indemnizacion_90_dias = 0
        if self.hr_causa_id.indemnizacion_90_dias and antig_anios >= 1.0:
            self.monto_indemnizacion_90_dias = 90.0 * self.sueldo_base_con_prevision_social
            if self.hr_causa_id.code == '10':
                self.monto_indemnizacion_90_dias += 6.0 * 30.4 * self.sueldo_base_con_prevision_social
            elif self.hr_causa_id.code == '11':  # ART: 54 LFT
                self.monto_indemnizacion_90_dias = 30.4 * self.sueldo_base_con_prevision_social
            elif self.hr_causa_id.code == '16':  # ART: 439 LFT + ART: 782 LFT
                self.monto_indemnizacion_90_dias = 4.0 * 30.4 * self.sueldo_base_con_prevision_social    
        
        #indemnizacion_20_dias - Contrato con Tiempo Indeterminado - ART: 50 FRACC. II LFT
        self.monto_indemnizacion_20_dias = 0
        if self.hr_causa_id.indemnizacion_20_dias and self.contract_id.sat_tipo_contrato_id.code=='01':
            self.monto_indemnizacion_20_dias = antig_anios * 20.0 * self.sueldo_base_con_prevision_social
        elif self.hr_causa_id.indemnizacion_20_dias and \
             self.contract_id.sat_tipo_contrato_id.code!='01' and \
             antig_anios >= 2.0 and self.hr_causa_id.code == '11':
            self.monto_indemnizacion_20_dias = (antig_anios - 1.0) * 20.0 * self.sueldo_base_con_prevision_social
        elif self.hr_causa_id.indemnizacion_20_dias and \
             self.contract_id.sat_tipo_contrato_id.code!='01' and \
             self.hr_causa_id.code == '16':
            self.monto_indemnizacion_20_dias = antig_anios * 20.0 * self.sueldo_base_con_prevision_social
        
        #prima_antiguedad_12_dias
        self.monto_prima_antiguedad_12_dias = 0
        if self.hr_causa_id.prima_antiguedad_12_dias and self.contract_id.sat_tipo_contrato_id.code=='01':
            self.monto_prima_antiguedad_12_dias = antig_anios * 12.0 * (self.sueldo_base_con_prevision_social if self.sueldo_base_con_prevision_social < (salario_minimo.monto * 2.0) else (salario_minimo.monto * 2.0))
            
        #prima_antiguedad_15_anios
        self.monto_prima_antiguedad_15_anios = 0
        if self.hr_causa_id.prima_antiguedad_15_anios and antig_anios >= 15:
            self.monto_prima_antiguedad_15_anios = antig_anios * 12.0 * (self.sueldo_base_con_prevision_social if self.sueldo_base_con_prevision_social < (salario_minimo.monto * 2.0) else (salario_minimo.monto * 2.0))    
        
        
        fecha_final = self.date
        fecha_inicial = self.contract_id.fecha_ingreso #self.contract_date_start
        if fecha_inicial.year < fecha_final.year: # Inicio del anio
            dias_trabajados = (fecha_final - datetime(fecha_final.year,1,1).date()).days +1
        else: # Mismo anio
            dias_trabajados = (fecha_final - fecha_inicial).days +1
        self.dias_trabajados = dias_trabajados
        if self.dias_aguinaldo and self.dias_aguinaldo >= 15:
            self.proporcional_aguinaldo_dias = dias_trabajados / 365.0 * self.dias_aguinaldo
            self.proporcional_aguinaldo = (self.sueldo_base_con_prevision_social) * (dias_trabajados / 365.0 * self.dias_aguinaldo)
        else:
            raise ValidationError(_("Advertencia!\nNo puede definir menos de 15 días para Aguinaldo"))
                                            
        concepto_vacaciones = self.env['hr.leave.type'].search([('name','=','VACACIONES')], limit=1)
        
        if self.company_id.crear_extra_prima_vacacional_en_aniversario=='1':
            self.dias_vacaciones_pendientes = 0
        else:
            vacaciones_x_disfrutar = self.env['hr.leave.allocation'].search([('employee_id','=',self.employee_id.id),
                                                                  ('holiday_type','=','employee'),
                                                                  ('state','=','validate'),
                                                                  ('vacaciones','=',True),
                                                                  ('holiday_status_id','=',concepto_vacaciones.id)
                                                                 ])

            self.dias_vacaciones_pendientes = sum(vacaciones_x_disfrutar.mapped('number_of_days_display'))
        
        
        if dias_trabajados:
            _antig = (self.antig_anios - (self.antig_anios % 1))+1
            prest_line = self.env['sat.nomina.tabla_prestaciones'].search([('antiguedad','=',_antig),('sindicalizado','=',self.contract_id.sindicalizado)], limit=1)

            if prest_line:
                dias = prest_line.dias_vacaciones
            else:
                xdias = self.env['sat.nomina.tabla_vacaciones'].search([('antiguedad','=',_antig)])
                dias = xdias and xdias.dias or 0
            
            fecha_final = self.date
            fecha_inicial = self.contract_id.fecha_ingreso #self.contract_date_start # Se toma la fecha de inicio del contrato para aquellos que trabajan por contrato aunque la fecha de ingreso sea previa
            if fecha_inicial.year == fecha_final.year: # Inicio Contrato mismo anio
                dias_para_vacaciones = (fecha_final - fecha_inicial).days + 1
            else:
                f_inicial = datetime(fecha_final.year-1, fecha_inicial.month, fecha_inicial.day).date()
                dias_para_vacaciones = (fecha_final - f_inicial).days + 1
            #proporcional = dias_para_vacaciones / (365.0 if self.date.year % 4.0 else 366.0)
            if self.env.company.antiguedad_finiquito_proporcionales:
                proporcional = self.antig_anios % 1
            else:
                proporcional = ((self.contract_date_end - self.contract_date_start).days / 365.0) % 1
            self.proporcional_vacaciones_dias = dias * proporcional
        if self.dias_vacaciones_pendientes or self.proporcional_vacaciones_dias:
            self.proporcional_vacaciones = (self.dias_vacaciones_pendientes + self.proporcional_vacaciones_dias) *\
                                            (self.sueldo_base_con_prevision_social)
        if not self.proporcional_prima_vac_dias:
            self.proporcional_prima_vac_dias = self.total_dias_vacaciones
        if self.proporcional_vacaciones or self.proporcional_prima_vac_dias:
            if self.proporcional_prima_vac_dias == self.total_dias_vacaciones:
                self.proporcional_prima_vacacional = self.proporcional_prima_vacacional_base * self.proporcional_vacaciones / 100.0
            else:
                self.proporcional_prima_vacacional = (self.proporcional_prima_vacacional_base / 100.0) * (self.proporcional_prima_vac_dias * self.sueldo_base_con_prevision_social)
        self.calculado = True
    
    
    
    def compute_data2(self):
        # monto_indemnizacion_90_dias
        antig_anios = round(self.antig_anios) if self.company_id.antiguedad_segun_lft=='1' else (self.antig_anios - (self.antig_anios % 1))

        dias_trabajados = self.dias_trabajados
        if self.dias_aguinaldo and self.dias_aguinaldo >= 15:
            self.proporcional_aguinaldo_dias = dias_trabajados / 365.0 * self.dias_aguinaldo
            self.proporcional_aguinaldo = self.sueldo_base_con_prevision_social * (dias_trabajados / 365.0 * self.dias_aguinaldo)
        else:
            raise ValidationError(_("Advertencia!\nNo puede definir menos de 15 días para Aguinaldo"))    
        concepto_vacaciones = self.env['hr.leave.type'].search([('name','=','VACACIONES')], limit=1)
        vacaciones_x_disfrutar = self.env['hr.leave'].search([('employee_id','=',self.employee_id.id),
                                                                 ('holiday_type','=','employee'),
                                                                 ('state','=','validate'),
                                                                 ('holiday_status_id','=',concepto_vacaciones.id)])
        
        if self.dias_vacaciones_pendientes or self.proporcional_vacaciones_dias:
            self.proporcional_vacaciones = (self.dias_vacaciones_pendientes + self.proporcional_vacaciones_dias) *\
                                            (self.sueldo_base_con_prevision_social)
        if self.proporcional_vacaciones or self.proporcional_prima_vac_dias:
            if self.proporcional_prima_vac_dias == self.total_dias_vacaciones:
                self.proporcional_prima_vacacional = self.proporcional_prima_vacacional_base * self.proporcional_vacaciones / 100.0
            else:
                self.proporcional_prima_vacacional = (self.proporcional_prima_vacacional_base / 100.0) * (self.proporcional_prima_vac_dias * self.sueldo_base_con_prevision_social)
    
    
    
    def create_extras_settlement(self, code=False, monto=0.0, tipo='percepcion', dias_vacaciones=0.0): # tipo: percepcion / deduccion / otrospagos
        if not monto:
            return
        extra_obj = self.env['hr.payslip.extra']
        tipo_concepto = {'percepcion': {'objeto': 'sat.nomina.tipopercepcion',
                                        'campo' : 'tipopercepcion_id'},
                         'deduccion' : {'objeto': 'sat.nomina.tipodeduccion',
                                        'campo' :'tipodeduccion_id'},
                         'otrospagos': {'objeto': 'sat.nomina.tipootropago',
                                        'campo' :'tipootropago_id'}
                        }
        salary_rule_obj = self.env['hr.salary.rule']
        objeto = self.env[tipo_concepto[tipo]['objeto']]
        concepto_sat = objeto.search([('code','=',code)], limit=1)
        if dias_vacaciones:
            concepto = salary_rule_obj.search([(tipo_concepto[tipo]['campo'],'=',concepto_sat.id),
                                               ('code','=','VACACIONES'), # Fix - Agregar check a Regla Salarial
                                               ('can_be_payroll_extra','=', True),
                                               ('nomina_aplicacion','=',tipo)], limit=1)
        else:
            concepto = salary_rule_obj.search([(tipo_concepto[tipo]['campo'],'=',concepto_sat.id),
                                               ('can_be_payroll_extra','=', True),
                                               ('nomina_aplicacion','=',tipo)], limit=1)

        if not concepto:
            raise ValidationError(_('Advertencia!\nNo existe la Regla Salarial para %s para Código %s\nRevise que tenga activo el check de "Se usa en Extras de Nómina"') % (tipo,code))
        
        data = {'settlement_id'     : self.id,
                'employee_id'       : self.employee_id.id,
                'hr_salary_rule_id' : concepto.id,
                'date'              : self.date,
                'qty'               : dias_vacaciones or 1.0,
               }
        
        extra = extra_obj.new(data)
        extra.onchange_employee()
        extra_data = extra._convert_to_write(extra._cache)
        extra_data['amount'] = monto# if not dias_vacaciones else self.contract_id.cfdi_sueldo_base
        if not extra_data.get('contract_id', False):
            raise ValidationError(_("Advertencia!\nEl Empleado no tiene Contrato válido para la fecha del Documento..."))
        rec = extra_obj.create(extra_data)
        rec.action_confirm()
        rec.action_approve()
    
    
    
    def compute_payslip(self):
        payslip_obj = self.env['hr.payslip']
        extra_obj = self.env['hr.payslip.extra']
        if self.payslip_id:
            self.payslip_id.with_context({'settlement_id' : self.id}).action_cancel()
            self.payslip_id = False
        if self.settlement_payslip_id:
            self.settlement_payslip_id.with_context({'settlement_id' : self.id}).action_cancel()
            self.settlement_payslip_id = False
            
        self.hr_payslip_extra_ids.write({'state' : 'cancel', 'payslip_id' : False})
        
        
        # Creamos los Extras de Nomina (Otros Ingresos)
        self.create_extras_settlement(code='021', 
                                      monto=self.proporcional_prima_vacacional, tipo='percepcion')
        self.create_extras_settlement(code='002', 
                                      monto=self.proporcional_aguinaldo, tipo='percepcion')
        self.create_extras_settlement(code='001', 
                                      monto=self.proporcional_vacaciones, tipo='percepcion', dias_vacaciones=self.total_dias_vacaciones)
        
        self.create_extras(self.other_income_ids)
        self.create_extras(self.discount_ids)
                        
        # Creamos la nomina regular
        #slip_data = payslip_obj._onchange_employee_id(self.date_from, self.date_to, 
        #                                             self.employee_id.id, contract_id=False)                    
        res = {
            'tiponomina_id' : self.env['sat.nomina.tiponomina'].search([('code','=','O')], limit=1).id,
            'date_payroll'  : self.date_payroll,
            'date'          : self.date_payroll,
            'employee_id'   : self.employee_id.id,
            'date_from'     : self.date_from,
            'date_to'       : self.date_to,
            'company_id'    : self.employee_id.company_id.id,
            'contract_id'   : self.contract_id.id,
            'struct_id'     : self.struct_id.id,
            'journal_id'    : self.journal_id.id,
            'settlement_id' : self.id,
        }

        payslip = payslip_obj.new(res)
        payslip._onchange_employee()
        res = payslip._convert_to_write(payslip._cache)
        res['struct_id'] = self.struct_id.id
        payslip_id = payslip_obj.create(res)
        payslip_id.with_context({'settlement_id' : self.id}).compute_sheet()
        self.payslip_id = payslip_id.id
        
        
        ##### NOMINA DE FINIQUITO ###
        if (self.suma_indemnizacion + self.suma_prima_antiguedad):
            self.create_extras_settlement(code='025', monto=self.suma_indemnizacion, tipo='percepcion')
            self.create_extras_settlement(code='022', monto=self.suma_prima_antiguedad, tipo='percepcion')
        
            #slip_data = payslip_obj.onchange_employee_id(self.date, self.date,
            #                                             self.employee_id.id, contract_id=False)
            res = {
                'tiponomina_id' : self.env['sat.nomina.tiponomina'].search([('code','=','E')], limit=1).id,
                'date_payroll'  : self.date_payroll_settlement,
                'date'          : self.date_payroll_settlement,
                'employee_id'   : self.employee_id.id,
                'date_from'     : self.date,
                'date_to'       : self.date,
                'company_id'    : self.employee_id.company_id.id,
                'contract_id'   : self.contract_id.id,
                'struct_id'     : self.settlement_struct_id.id,
                'journal_id'    : self.journal_id.id,
                'settlement_id' : self.id,
                }

            payslip = payslip_obj.new(res)
            payslip._onchange_employee()
            res = payslip._convert_to_write(payslip._cache)
            res['struct_id'] = self.settlement_struct_id.id
            payslip_id = payslip_obj.create(res)
            payslip_id.with_context({'settlement_id' : self.id}).compute_sheet()
            self.settlement_payslip_id = payslip_id.id
        
        return True

    
    
    def action_confirm(self):
        for rec in self:
            #rec.compute_payslip()
            if not rec.payslip_id or rec.payslip_id.state=='cancel':
                raise UserError(_("Error de Usuario.\nNo puede confirmar el documento sin antes haber calculado los conceptos"))
            if rec.neto_a_pagar < 0:
                raise UserError(_("Error de Datos.\nNo puede confirmar el documento con Neto a Pagar negativo"))
        self.write({'state': 'confirmed'})
        return True
    
    
    def action_done(self):
        for rec in self:
            rec.payslip_id.action_payslip_done()
            rec.settlement_payslip_id.action_payslip_done()
            rec.write({'state': 'done'})
            rec.employee_id.write({'active':False})
            rec.contract_id.write({'state':'baja', 'active':False})
            self.env.cr.commit()
        return True
    
    
    def action_cancel(self):
        for rec in self:
            rec.payslip_id.with_context({'settlement_id' : rec.id}).action_cancel()
            rec.settlement_payslip_id.with_context({'settlement_id' : rec.id}).action_cancel()
            rec.hr_payslip_extra_ids.action_cancel()
        self.write({'state': 'cancel'})
        return True
    
    
class hr_settlement_other_income(models.Model):
    _name="hr.settlement.other_income"
    _description="Finiquitos - Otros Ingresos"    
    
    settlement_id = fields.Many2one('hr.settlement', string="Finiquito / Liquidación", 
                                    required=True, index=True)
    hr_salary_rule_id = fields.Many2one('hr.salary.rule', string='Concepto', required=True)
    
    amount              = fields.Float(string='Monto', digits=(18,2), default=0, required=True)
    
    
class hr_settlement_discounts(models.Model):
    _name="hr.settlement.discounts"
    _description="Finiquitos - Descuentos"
    
    
    settlement_id = fields.Many2one('hr.settlement', string="Finiquito / Liquidación", required=True,
                                   index=True)    
    hr_salary_rule_id = fields.Many2one('hr.salary.rule', string='Concepto', required=True)
    
    amount              = fields.Float(string='Monto', digits=(18,2), default=0, required=True)
    
    
