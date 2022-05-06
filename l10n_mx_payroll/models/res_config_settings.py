# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    registro_patronal = fields.Char('Registro Patronal',
                                    related="company_id.registro_patronal", readonly=False,
                                    help="Capture el Registro Patronal entregado por el IMSS sin guiones ni espacios")
    
    version_de_cfdi_para_nominas = fields.Selection(related="company_id.version_de_cfdi_para_nominas", readonly=False)
    
    factor_riesgo_ids = fields.One2many(related="company_id.factor_riesgo_ids", readonly=False)
    
    infonavit_importe_seguro_ids = fields.One2many(related="company_id.infonavit_importe_seguro_ids", readonly=False)
    
    antiguedad_finiquito_proporcionales = fields.Boolean(
        related="company_id.antiguedad_finiquito_proporcionales", readonly=False)
    
    extras_dentro_de_periodo_de_nomina = fields.Selection(
        related="company_id.extras_dentro_de_periodo_de_nomina", readonly=False)
    
    antiguedad_finiquito = fields.Selection(
        related="company_id.antiguedad_finiquito", readonly=False)
    
    antiguedad_segun_lft = fields.Selection(
        related="company_id.antiguedad_segun_lft", readonly=False)
    
    crear_extra_prima_vacacional_en_aniversario = fields.Selection(
        related="company_id.crear_extra_prima_vacacional_en_aniversario", readonly=False)
    
    prima_vacacional_salary_rule_id = fields.Many2one(
        'hr.salary.rule', string="Concepto Prima Vacacional",
        related="company_id.prima_vacacional_salary_rule_id", readonly=False)

    dias_despues_de_aniversario_para_pagar_prima_vacacional = fields.Integer(
        string="Días después de aniversario para pagar Prima Vacacional",
        related="company_id.dias_despues_de_aniversario_para_pagar_prima_vacacional", readonly=False,
        help="Indique cuantos días, posterior al aniversario, se pagarán los Días por Prima Vacacional")
    
    aplicar_calculo_inverso = fields.Boolean(
        string="Aplicar cálculo inverso",
        related="company_id.aplicar_calculo_inverso", readonly=False,
        help="Parametro para indicar si se debe hacer el cálculo inverso para los conceptos \n"
        "seleccionados. Se sumarán los conceptos y sobre ese monto se recalcularán los \n"
        "montos según su representación porcentual")
    
    reglas_para_calculo_inverso_ids = fields.Many2many(
        string="Reglas Salariales a aplicar Cálculo Inverso",
        related="company_id.reglas_para_calculo_inverso_ids", readonly=False,
        help="Seleccione las reglas salariales que se tomarán para aplicar Cálculo Inverso"
    )
    
    reprogramar_extras_al_eliminar_de_nomina = fields.Boolean(
        string="Re-Programar Extras de Nómina al quitarlos de una Nómina en Borrador",
        related="company_id.reprogramar_extras_al_eliminar_de_nomina", readonly=False,
        help="Parametro para indicar si en una Nómina en Borrador al eliminar una Entrada \n"
        "(Otras Entradas) ligada a un Extra de Nómina entonces se abra un wizard para \n"
        "re-programar el Extra de Nómina para que no se pierdan.")

    dias_para_vencimiento_de_vacaciones = fields.Integer(
        string="Días para vencimiento de Vacaciones",
        related="company_id.dias_para_vencimiento_de_vacaciones", readonly=False,
        help="Indique cuantos días posteriores al vencimiento de las Vacaciones  quiere \n"
        "mantenerlas disponibles para el trabajador"
    )
    
    maximo_de_nominas_a_generar_en_batch = fields.Integer(
        string="Número Máximo de Nóminas a Generar en Batch",
        related="company_id.maximo_de_nominas_a_generar_en_batch", readonly=False,
        help="Indique el máximo de Nóminas a Generar cuando se creen desde Lotes de Nóminas\n"
        "Por defecto 0 significa sin límite"
    )
    
    reglas_a_incluir_en_periodo_de_nomina_finiquito_ids = fields.Many2many(
        related="company_id.reglas_a_incluir_en_periodo_de_nomina_finiquito_ids", readonly=False,
    )