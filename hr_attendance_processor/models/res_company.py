# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    
    hr_attendance_retardo_por_minuto = fields.Selection(
        [('1', 'Se descuentan los minutos del retardo'),
         ('2', 'No se descuentan')],
        string="Descontar minutos de retardo", default='2',
        help="""Parámetro para indicar si se generan descuentos por minuto tomando en cuenta el parámetro """
             """de Tolerancia para Retardo; si el trabajador llega después de la hora de entrada """
             """pero antes de esa tolerancia entonces se debe generar un registro de Extra de Nómina """
             """ para descontar los minutos.""")
    
    hr_attendance_retardo_salary_rule_id = fields.Many2one(
        'hr.salary.rule', string="Concepto para descontar minutos de retardo",
        help="""Parametro para indicar la Regla Salarial a usarse para generar los descuentos """
             """por minuto tomando en cuenta el parámetro de Mins. Tolerancia para Retardo; """
             """si el trabajador llega después de la hora de entrada según el Horario que tenga """
             """asignado pero antes de esa tolerancia entonces se debe generar un registro de """
             """Extra de Nómina para poder descontar los minutos.""")
    
    
    hr_attendance_dia_inicio_periodo_semanal = fields.Selection(
        [('0', 'Lunes'),
         ('1', 'Martes'),
         ('2', 'Miércoles'),
         ('3', 'Jueves'),
         ('4', 'Viernes'),
         ('5', 'Sábado'),
         ('6', 'Domingo')],
        string="Día de Inicio de Periodo Semanal", default='2',
        help="""Parámetro para indicar el día de la semana que es inicio del periodo para las """
             """Nóminas Semanales; solo es útil si usa Nómina Semanal.""")
    
    hr_attendance_considerar_retardos_en_periodo = fields.Selection(
        [('1', 'Todo el mes'),
         ('2', 'Solo en el periodo de la nómina')],
        string="Considerar Retardos en Periodo", default='2',
        help="""Parámetro para indicar si los retardos se consideran para todo el mes o solo en el """
             """periodo de Nóminas. Si no considera los retardos para todo el mes entonces solo aplicaría """
             """para Nómina Semanal y/o Quincenal (1-15 + 16-Fin de Mes).""")
    
    hr_attendance_retardos_para_una_falta = fields.Integer(
        string="# Retardos que generan Falta", default=3,
        help="""Parámetro para indicar el  Número de Retardos en el Periodo que me generan una falta.""")
    
    hr_attendance_minutos_tolerancia_retardo = fields.Integer(
        string="Mins. Tolerancia Retardo", default=10,
        help="""Parámetro para indicar los minutos de Tolerancia antes de considerarse como retardo. """
            """ Considere un valor razonable no mayor a 30 minutos.""")
        
    hr_attendance_minutos_retardo_genera_falta = fields.Integer(
        string="Mins. Retardo que genera Falta", default=45,
        help="""Parámetro para indicar los minutos para considerarse un retardo que genera una Falta. """
            """ Considere un valor razonable no mayor a 60 minutos.""")
    
    hr_attendance_minutos_tolerancia_hrs_extra = fields.Integer(
        string="Horas Extras - Mins. después de Salida", default=45,
        help="""Parámetro para indicar los minutos después de la Hora de Salida para considerarse como """
             """Horas Extras. """
             """Considere un valor razonable no mayor a 60 minutos.""")
        
    hr_attendance_hrs_extra_desde_tolerancia = fields.Selection(
        [('1', 'Considerar Minutos después de Salida'),
         ('2', 'Hrs. Extra desde la Hora de Salida del Horario')],
        string="Horas extras sumando Mins. después de Salida", default='2',
        help="""Parámetro para indicar si se generan las Horas Extras sumando el valor del parámetro """
             """<Horas Extras - Mins. después de Salida> para que a partir de allí se calculen las """
             """las Horas Extras.""")

    hr_attendance_minutos_tolerancia_salida = fields.Integer(
        string="Mins. Tolerancia antes de Horario Salida", default=5,
        help="""Parámetro para indicar los minutos Máximo previos a la hora de salida. """
             """Si sobrepasa el máximo se genera falta del día.""")
    
