# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import math
import logging
_logger = logging.getLogger(__name__)


class HRContractMovimientosPermanentes(models.Model):
    _name = 'hr.contract.movs_permanentes'
    _description = 'Movimientos Permanentes de Empleados hacia Nomina'
    _rec_name = 'hr_salary_rule_id'
    
    contract_id = fields.Many2one('hr.contract', string="Contrato", required=True, index=True)
    hr_salary_rule_id = fields.Many2one('hr.salary.rule', string="Concepto", required=True)
    amount      = fields.Float(string='Monto', digits=(18,4), default=0, required=True)
    move_type = fields.Selection([('fixed','Monto Fijo'),
                                  ('percent','Porcentaje'),
                                  ('python','Código Python')],
                                string="Tipo", default='fixed', required=True
                                )
    
    python_code = fields.Text(string="Código Python")
    
    notes       = fields.Text(string="Notas")
    
    _sql_constraints = [
        ('contract_id_salary_rule_id', 'unique(contract_id,hr_salary_rule_id)','El Concepto para el Movimiento Permanente debe ser único'),
        ('check_amount', 'CHECK(amount > 0)',
         'El monto del Movimiento Permanente debe ser mayor a cero.')
    ]

class HRContractSDI(models.Model):
    _name = 'hr.contract.sdi'
    _description = "Historial de SDIs del contrato / trabajador"
    _order = 'date desc'
    
    contract_id = fields.Many2one('hr.contract', string="Contrato", required=True, index=True, ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', string="Empleado", related='contract_id.employee_id', readonly=True,
                                 store=True)
    date        = fields.Date(string="Fecha", default=fields.Date.context_today, index=True, required=True)
    amount      = fields.Float(string='SBC', digits=(18,4), default=0, required=True)
    notes       = fields.Text(string="Notas")

    _sql_constraints = [
        #('contract_id_date_amount_unique', 'unique(contract_id,date)','El registro del SBC debe ser único en la fecha, ya existe un registro en esta fecha'),
        ('check_amount', 'CHECK(amount > 0)', 'El monto del SBC debe ser mayor a cero.')
    ]


class HRContract(models.Model):
    _inherit = 'hr.contract'
    
    
    
    @api.depends('sdi_ids', 'cfdi_sueldo_base', 'sindicalizado','fecha_ingreso')
    def _get_current_sdi(self):
        dias_aguinaldo = 15
        tabla_vacaciones_obj = self.env['sat.nomina.tabla_vacaciones']
        tabla_prestaciones_obj = self.env['sat.nomina.tabla_prestaciones']
        for rec in self:
            dias = (fields.Date.context_today(self) - rec.fecha_ingreso).days + 1
            antig_anios = dias / 365.0
            antig_4_vacaciones = math.ceil(antig_anios)
            
            vac_line = tabla_vacaciones_obj.search([('antiguedad','=',antig_4_vacaciones)], limit=1)
            dias_vacaciones = vac_line and vac_line.dias or 0
            dias_aguinaldo = 15 # Por ley
            prima_vacacional = 25.0 # Por ley
            prest_line = tabla_prestaciones_obj.search([('antiguedad','=',antig_4_vacaciones),
                                                        ('sindicalizado','=',rec.sindicalizado)], limit=1)
            if prest_line:
                dias_vacaciones = prest_line.dias_vacaciones
                prima_vacacional= prest_line.prima_vacacional
                dias_aguinaldo  = prest_line.dias_aguinaldo
            
            
            monto_aguinaldo = dias_aguinaldo * rec.cfdi_sueldo_base
            monto_prima_vacacional = rec.cfdi_sueldo_base * dias_vacaciones * prima_vacacional / 100.0
            #_logger.info("\nParametros:\ndias_vacaciones: %s\nPrima Vacacional: %s\nDias Aguinaldo: %s\n------------------------\nmonto_aguinaldo: %s\nmonto_prima_vacacional: %s\ncfdi_sueldo_base: %s" % (dias_vacaciones, prima_vacacional, dias_aguinaldo, monto_aguinaldo,monto_prima_vacacional, rec.cfdi_sueldo_base))
            if rec.sdi_ids:
                rec.cfdi_factor_salario_diario_integrado = rec.cfdi_sueldo_base and rec.sdi_ids[0].amount / rec.cfdi_sueldo_base or 0
            else:
                rec.cfdi_factor_salario_diario_integrado = rec.cfdi_sueldo_base and \
                                                        (((rec.cfdi_sueldo_base * 365.0) + monto_aguinaldo + monto_prima_vacacional) / (rec.cfdi_sueldo_base * 365.0)) or 0
                
            
            rec.cfdi_salario_diario_integrado = rec.cfdi_sueldo_base  and \
                                                        (((rec.cfdi_sueldo_base * 365.0) + monto_aguinaldo + monto_prima_vacacional) / 365.0) or 0
            rec.cfdi_salario_diario_integrado2 = rec.sdi_ids and rec.sdi_ids[0].amount or rec.cfdi_salario_diario_integrado
            #rec.cfdi_factor_salario_diario_integrado = rec.cfdi_sueldo_base and (rec.cfdi_salario_diario_integrado2 / rec.cfdi_sueldo_base) or 0

            try:
                rec.cfdi_sueldo_base_con_prevision = eval(rec.calculo_prevision_social % rec.cfdi_sueldo_base)
            except:
                rec.cfdi_sueldo_base_con_prevision = rec.cfdi_sueldo_base
            
    
    
    @api.depends('date_start')
    def _compute_contract_data(self):
        for rec in self:
            #rec.cfdi_salario_diario_integrado = rec.cfdi_factor_salario_diario_integrado * rec.cfdi_sueldo_base
            rec.sat_antiguedad = 'P2Y4M12D' # TODO
            
    @api.depends('structure_type_id')
    def _get_tipo_sueldo(self):
        for rec in self:
            if not rec.structure_type_id:
                rec.tipo_sueldo= 'diario'
            else:
                rec.tipo_sueldo = rec.structure_type_id.wage_type=='monthly' and 'diario' or 'hora'
        
    prestaciones = fields.Text(string="Prestaciones")
    is_template = fields.Boolean(string="Es Plantilla", default=False, index=True)
    
    state = fields.Selection(selection_add=[('baja', 'Baja')])
    
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura Salarial', 
                                tracking=True, required=False) 
    job_id = fields.Many2one('hr.job', tracking=True, readonly=False,
                             related="employee_id.job_id")
    
    department_id = fields.Many2one('hr.department', tracking=True, readonly=False, store=True,
                                    related="employee_id.department_id")
    

    date_start = fields.Date('Start Date', required=True, default=fields.Date.today,
                             tracking=True,
                             help="Start date of the contract.")
    date_end = fields.Date('End Date',
                           tracking=True,
                           help="End date of the contract (if it's a fixed-term contract).")
    
    fecha_ingreso = fields.Date(string="Fecha Ingreso", default=fields.Date.context_today, 
                                tracking=True,
                                index=True, required=True,
                                help="Use esta fecha para definir la Fecha de Ingreso del Trabajador para cuestiones de Antigüedad")
    
    movs_permanentes_ids = fields.One2many('hr.contract.movs_permanentes', 'contract_id', copy=True,
                                           string="Movimientos Permanentes")
    
    sdi_ids = fields.One2many('hr.contract.sdi', 'contract_id', string="SDIs", copy=False)
    sat_antiguedad = fields.Char('Antigüedad', compute="_compute_contract_data")
    sat_tipo_contrato_id = fields.Many2one('sat.nomina.tipocontrato', string="SAT Tipo Contrato", 
                                           required=False, tracking=True)

    calculo_prevision_social = fields.Char(string="Previsión Social", required=True, 
                                           help="Indique la fórmula para calcular el Sueldo con Previsión Social\n"
                                                "Ej. (%s * 1.1) => Esto aplicaría cuando entrega un bono de puntualidad del 10%)",
                                           tracking=True, default='%s')
    
    sat_periodicidadpago_id = fields.Many2one('sat.nomina.periodicidadpago', string="Periodicidad Pago",
                                             tracking=True, required=False)
    sat_tipojornada_id = fields.Many2one('sat.nomina.tipojornada', string="Jornada Laboral",
                                        tracking=True, required=False)
    sat_tiporegimen_id = fields.Many2one('sat.nomina.tiporegimen', string="Regimen Laboral",
                                        tracking=True, required=False)
    sat_riesgopuesto_id      = fields.Many2one('sat.nomina.riesgopuesto', 'Tipo Riesgo Puesto',
                                               tracking=True, required=False,
                                               help="Catálogo de clases de Riesgo en que deben inscribirse los patrones.")
    # hr.settlement    
    cfdi_sueldo_base_con_prevision = fields.Float('Sueldo con Previsión Social', digits=(18,4), 
                                                  compute="_get_current_sdi", compute_sudo=True)
    
    cfdi_sueldo_base = fields.Float('Sueldo', digits=(18,4), default=0,
                                    tracking=True, required=True,
                                    help="""Salario diario registrado ante el IMSS. Este se toma como\n"""
                                         """base para los cálculos de Percepciones y Deducciones\n"""
                                         """Puede ser Diario, por Hora, o según corresponda.""")
    cfdi_factor_salario_diario_integrado = fields.Float(string='Factor SDI', digits=(18,6), #default=1.0452,
                                                        tracking=True,
                                                        compute='_get_current_sdi', compute_sudo=True,
                                                        help="Factor para cálculo de Salario Diario Integrado")
    
    cfdi_salario_diario_integrado = fields.Float(string='SDI', digits=(18,2), default=0, store=True,
                                                help="Salario Diario Integrado",
                                                compute="_get_current_sdi", compute_sudo=True)
    cfdi_salario_diario_integrado2 = fields.Float('SBC', digits=(18,2), store=True,
                                                  compute="_get_current_sdi", tracking=True,
                                                  compute_sudo=True,
                                                  help="""Salario Base de Cotización usado para cálculos del IMSS.""")
    wage_type = fields.Selection(related="structure_type_id.wage_type", readonly=True)
    tipo_sueldo = fields.Selection([('hora','Por Hora'),
                                    ('diario','Diario')],
                                  string="Tipo Salario", compute="_get_tipo_sueldo")
    
    dias_aguinaldo = fields.Integer(string="Días para Aguinaldo", default=15,
                                    tracking=True,
                                    help="Días que se usarán para calcular el Salario Diario Integrado\n"
                                         "y el Aguinaldo en Diciembre")
    
    dias_vacaciones = fields.Integer(string="Días Vacaciones", 
                                     tracking=True,
                                     help="Días que se usarán para calcular el Salario Diario Integrado\n"
                                          "y el Aguinaldo en Diciembre")
    
    prima_vacacional= fields.Float(string="Prima Vacacional", default=25.0,
                                   tracking=True,
                                   help="Porcentaje a usar como Prima Vacacional, por ley mínimo es 25%")
    
    sindicalizado = fields.Selection([('Si','Sindicalizado'),
                                      ('No','De Confianza')],
                                     tracking=True,
                                     string="Sindicalizado", default='No')
    
    leave_ids = fields.One2many('hr.leave', 'contract_id', string="Ausencias relacionadas")
    
    #company_id = fields.Many2one('res.company', string='Compañía', 
    #                                      default=lambda self: self.env['res.company']._company_default_get('hr.contract'))
    
    tipo_salario_minimo = fields.Selection([('smg', 'Salario Mínimo General'),
                                            ('smfn', 'Salario Mínimo Frontera Norte'), 
                                           ], string="Zona Salario Mínimo", tracking=True,
                                           required=True, default='smg')
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        contracts = self.filtered(lambda c: c.date_end and c.date_start > c.date_end)
        if contracts:
            contratos = []
            for c in contracts:
                contratos.append("Contrato:  %s - %s - Fecha Inicial: %s - Fecha Final: %s" % (c.id, c.name, c.date_start, c.date_end))
            if contratos:
                raise ValidationError(_('La Fecha Inicial no debe ser mayor a la Fecha Final. Revise los siguientes contratos:\n%s' % '\n'.join(contratos)))
            #raise ValidationError(_('La Contract start date must be earlier than contract end date.'))
            
    @api.constrains('prima_vacacional')
    def _check_prima_vacacional(self):
        if self.filtered(lambda c: c.prima_vacacional < 25):
            raise ValidationError(_('El Porcentaje de Prima Vacacional no puede ser menor a 25%.'))
            
    
    @api.onchange('schedule_pay')
    def _onchange_schedule_pay(self):
        if self.schedule_pay:
            data = {'dayly'     : '01', 'weekly'    : '02', 'two-weeks' : '03',
                    'bi-weekly' : '04', 'monthly'   : '05', 'bi-monthly': '06',
                    'piecework' : '07', 'commission': '08', 'priceraised': '09',
                    'ten-days'  : '10', 'other'     : '99',
                   }
            res = self.env['sat.nomina.periodicidadpago'].search([('code','=',data[self.schedule_pay])], limit=1)
            self.sat_periodicidadpago_id = res.id
        else:
            self.sat_periodicidadpago_id = False

                    
    
    def _faltas_periodo_anual(self, fecha):
        self.ensure_one()
        reglas = self.env['hr.salary.rule'].search([('category_id.code','in',('FALTAS','FALTAS_SIN_GOCE','INCAP_ENFERMEDAD_GENERAL'))])
        faltas = self.env['hr.payslip.extra'].search([('employee_id','=',self.employee_id.id),
                                                      ('state','=','done'),
                                                      ('date','>=', date(fecha.year,1,1)),
                                                      ('hr_salary_rule_id', 'in', reglas.ids)]) 
        return sum(faltas.mapped('qty'))

    
    def write(self, vals):
        contratos = []
        for rec in self:
            if 'cfdi_sueldo_base' in vals and rec.cfdi_sueldo_base != vals['cfdi_sueldo_base'] and \
               'state' not in vals and rec.state in ('open','draft') and rec.cfdi_salario_diario_integrado2:
                contratos.append({'contract_id' : rec.id, 
                                  'variable' : rec.cfdi_salario_diario_integrado2 - rec.cfdi_salario_diario_integrado})
        res = super(HRContract, self).write(vals)
        _logger.info("contratos: %s" % contratos)
        if contratos:
            contract_obj = self.env['hr.contract']
            sdi_obj = self.env['hr.contract.sdi']
            for c in contratos:
                #_logger.info("c: %s" % (c))
                contrato = contract_obj.browse(c['contract_id'])
                sdi = contrato.cfdi_salario_diario_integrado + c['variable']
                xres = sdi_obj.create({'contract_id' : c['contract_id'],
                        'amount'      : sdi,
                        'notes'       : _('Modificación de Salario')})
        return res
