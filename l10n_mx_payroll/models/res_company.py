# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    
    registro_patronal   = fields.Char('Registro Patronal')
    factor_riesgo_ids = fields.One2many('hr.riesgo_trabajo', 'company_id', string='Riesgo de Trabajo')
    infonavit_importe_seguro_ids = fields.One2many('hr.infonavit.importe_seguro', 'company_id', 
                                                   string='Infonavit Importe Seguro')
    
    version_de_cfdi_para_nominas = fields.Selection(
        [('3.3','CFDI 3.3'),
         ('4.0','CFDI 4.0')],
        string="Versión de CFDI a Usar", default='3.3',
        help="Seleccione cuál es la versión de CFDI que emitirá para Nóminas"
    )
    
    antiguedad_finiquito_proporcionales = fields.Boolean(
        string="Finiquito Antigüedad", default=True,
        help="Active si quiere agregar un día para el cálculo de la Antigüedad"
    )
    
    extras_dentro_de_periodo_de_nomina = fields.Selection(
        [('1', '1- Con Fecha Inicial y Final dentro del Periodo'),
         ('2', '2- Hasta Fecha Final del Periodo')],
        string="Extras de Nómina en Periodo de Nómina",
        help="1- Solo se incluirán los Extras de Nómina con fecha dentro del Periodo de Nómina.\n"
        "2- Se incluyen los Extras de Nómina hasta la Fecha Final del Periodo no incluídos en Nóminas Previas",
        default='1')
    
    antiguedad_finiquito = fields.Selection(
        [('1', 'Fecha Inicio Contrato'),
         ('2', 'Fecha Ingreso')],
        string="Calcular Antigüedad desde:",
        help="Seleccione la forma en que se calcula la Antigüedad del trabajador.\n"
        "Esto aplica al cálculo del Finiquito.",
        default='2')
    antiguedad_segun_lft = fields.Selection(
        [('1', 'Redondear Arriba => (P.Ej: 1.4 = 1 año ó 1.6 = 2.0 año(s)'),
         ('2', 'Redondear Abajo  => (P.Ej: 1.4 = 1 año ó 1.6 = 1.0 año')],
        string="Finiquito - Antigüedad",
        help="Seleccione la forma en que se tomará la Antigüedad del trabajador.\n"
        "Esto aplica al cálculo del Finiquito.",
        default='1')
    
    crear_extra_prima_vacacional_en_aniversario = fields.Selection(
        [('1', 'SI = Crear Extra de Nómina para Prima Vacacional'),
         ('2', 'NO = Pagar Prima cuando disfrute vacaciones')],
        string="Pagar Prima Vacacional en Aniversario",
        default='2')
    
    prima_vacacional_salary_rule_id = fields.Many2one(
        'hr.salary.rule', string="Concepto Prima Vacacional",
        help="Parametro para indicar la Regla Salarial a usarse para generar los Extras de Nómina \n"
        "para la Prima Vacacional a pagar cuando el trabajador cumpla aniversario.\n"
        "Generalmente el concepto es algo parecido a Días de Vacaciones (Prima Vacacional en Aniversario)")
    
    dias_despues_de_aniversario_para_pagar_prima_vacacional = fields.Integer(
        string="Días después de aniversario para pagar Prima Vacacional",
        default=0,
        help="Indique cuantos días, posterior al aniversario, se pagarán los Días por Prima Vacacional"
    )
    
    aplicar_calculo_inverso = fields.Boolean(
        string="Aplicar cálculo inverso",
        default=0,
        help="Parametro para indicar si se debe hacer el cálculo inverso para los conceptos \n"
        "seleccionados. Se sumarán los conceptos y sobre ese monto se recalcularán los \n"
        "montos según su representación porcentual")
    
    reglas_para_calculo_inverso_ids = fields.Many2many(
        'hr.salary.rule', 'company_id_salary_rule_id_rel', 'company_id','salary_rule_id',
        string="Reglas Salariales a aplicar Cálculo Inverso",
        domain="[('nomina_aplicacion','=','percepcion')]",
        help="Seleccione las reglas salariales que se tomarán para aplicar Cálculo Inverso"
    ) 
    
    reprogramar_extras_al_eliminar_de_nomina = fields.Boolean(
        string="Re-Programar Extras de Nómina al quitarlos de una Nómina en Borrador",
        default=True,
        help="Parametro para indicar si en una Nómina en Borrador al eliminar una Entrada \n"
        "(Otras Entradas) ligada a un Extra de Nómina entonces se abra un wizard para \n"
        "re-programar el Extra de Nómina para que no se pierdan.")
    
    dias_para_vencimiento_de_vacaciones = fields.Integer(
        string="Días para vencimiento de Vacaciones",
        default=0,
        help="Indique cuantos días posteriores al vencimiento de las Vacaciones quiere \n"
        "mantenerlas disponibles para el trabajador"
    )
    
    maximo_de_nominas_a_generar_en_batch = fields.Integer(
        string="Número Máximo de Nóminas a Generar en Batch",
        default=0, required=True,
        help="Indique el máximo de Nóminas a Generar cuando se creen desde Lotes de Nóminas\n"
        "Por defecto 0 significa sin límite"
    )
    
    reglas_a_incluir_en_periodo_de_nomina_finiquito_ids = fields.Many2many(
        'hr.salary.rule', 'company_id_salary_rule_id_finiq_rel', 'company_id','salary_rule_id',
        string="Filtrar Reglas Salariales solo en periodo de Nómina (Finiquito)",
        help="""Seleccione las reglas salariales que solo deben tomarse en el periodo de la Nómina (de Finiquito) y descartar cualquier Extra de Nómina posterior al periodo de la Nómina. Esto aplica para conceptos como Fonacot."""
    )
class HRRiesgoTrabajo(models.Model):
    _name = 'hr.riesgo_trabajo'
    _description = "Factor de Riesgo de Trabajo"    
    _order = "vigencia desc"

    
    @api.depends('vigencia', 'factor')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia:
                rec.name = _('Vigente desde: ') + rec.vigencia.strftime('%Y-%m-%d') + (_(' - Factor: %s') % rec.factor)
            else:
                rec.name = _('Vigencia sin definir ')
            
    name = fields.Char('Referencia', store=True, compute='_compute_name')
    factor = fields.Float('Factor', digits=(18,6), required=True, default=0.0)
    vigencia        = fields.Date('Vigencia', required=True)
    notas   = fields.Text(string="Notas")
    company_id  = fields.Many2one('res.company', string="Compañía", required=True,
                                  default=lambda self: self.env['res.company']._company_default_get('hr.riesgo_trabajo'))

    _sql_constraints = [
        ('company_vigencia_unique', 'unique(company_id, vigencia)','El registro debe ser único')]
    
    

class HRInfonavitImporteSeguro(models.Model):
    _name = 'hr.infonavit.importe_seguro'
    _description = "Infonavit Importe Seguro"    
    _order = "vigencia desc"

    
    @api.depends('vigencia', 'factor')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia:
                rec.name = _(' Vigente desde: ') + rec.vigencia.strftime('%Y-%m-%d') + (_(' - Monto: %s') % rec.factor)
            else:
                rec.name = _('Vigencia sin definir ')
            
    name = fields.Char('Referencia', store=True, compute='_compute_name')
    factor = fields.Float('Monto', digits=(18,6), required=True, default=0.0)
    vigencia        = fields.Date('Vigencia', required=True)
    notas   = fields.Text(string="Notas")
    company_id  = fields.Many2one('res.company', string="Compañía", required=True,
                                  default=lambda self: self.env['res.company']._company_default_get('hr.riesgo_trabajo'))

    _sql_constraints = [
        ('company_vigencia_unique', 'unique(company_id, vigencia)','El registro debe ser único')]    
