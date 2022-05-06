# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    hr_attendance_retardo_por_minuto = fields.Selection(
        related='company_id.hr_attendance_retardo_por_minuto', readonly=False)
    
    hr_attendance_retardo_salary_rule_id = fields.Many2one(
        'hr.salary.rule', string="Concepto para descontar minutos de retardo",
        related='company_id.hr_attendance_retardo_salary_rule_id', readonly=False)
    
    
    hr_attendance_dia_inicio_periodo_semanal = fields.Selection(
        related='company_id.hr_attendance_dia_inicio_periodo_semanal', readonly=False)
    
    hr_attendance_considerar_retardos_en_periodo = fields.Selection(
        related='company_id.hr_attendance_considerar_retardos_en_periodo', readonly=False)
    
    hr_attendance_retardos_para_una_falta = fields.Integer(
        related='company_id.hr_attendance_retardos_para_una_falta', readonly=False)
    
    hr_attendance_minutos_tolerancia_retardo = fields.Integer(
        related='company_id.hr_attendance_minutos_tolerancia_retardo', readonly=False)
        
    hr_attendance_minutos_retardo_genera_falta = fields.Integer(
        related='company_id.hr_attendance_minutos_retardo_genera_falta', readonly=False)
    
    hr_attendance_minutos_tolerancia_hrs_extra = fields.Integer(
        related='company_id.hr_attendance_minutos_tolerancia_hrs_extra', readonly=False)
        
    hr_attendance_hrs_extra_desde_tolerancia = fields.Selection(
        related='company_id.hr_attendance_hrs_extra_desde_tolerancia', readonly=False)

    hr_attendance_minutos_tolerancia_salida = fields.Integer(
        related='company_id.hr_attendance_minutos_tolerancia_salida', readonly=False)
    
