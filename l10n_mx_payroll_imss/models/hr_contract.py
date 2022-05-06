# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
        
    
class HRContract(models.Model):
    _inherit = 'hr.contract'
    
    
    tipo_salario = fields.Selection([('0', 'Fijo'),
                                     ('1', 'Variable'),
                                     ('2', 'Mixto')], 
                                    string="Tipo de Salario",
                                    default='0', required=False, index=True, tracking=True)
    tipo_trabajador = fields.Selection([('1', 'Permanente'),
                                        ('2', 'Eventual Ciudad'),
                                        ('3', 'Eventual Construcción'),
                                        ('4', 'Eventual de Campo')], 
                                    string="Tipo de Trabajador",
                                    default='1', required=False, index=True, tracking=True)
    jornada_reducida = fields.Selection([('0', 'Normal'),
                                         ('1', '1 Día'),
                                         ('2', '2 Días'),
                                         ('3', '3 Días'),
                                         ('4', '4 Días'),
                                         ('5', '5 Días'),
                                         ('6', 'Jornada Reducida')], 
                                    string="Tipo de Jornada",
                                    default='0', required=True, index=True, tracking=True)
    
    tipo_pension = fields.Selection([('0', 'Sin Pensión'),
                                     ('1', 'Pensión en Invalidez y Vida'),
                                     ('2', 'Pensión en Cesantía y Vejez')], 
                                    string="Tipo de Pensión",
                                    default='0', required=True, index=True, tracking=True)
    
    @api.depends('fecha_ingreso', 'date_start')
    def _get_fecha_ingreso_vs_date_start(self):
        for l in self:
            l.fecha_ingreso_vs_date_start = bool(l.fecha_ingreso==l.date_start)
    
    fecha_ingreso_vs_date_start = fields.Boolean(string="Fecha Ingreso=Fecha Inicio",
                                                compute="_get_fecha_ingreso_vs_date_start",
                                                store=True)
    
class HRContractSDI(models.Model):
    _inherit = 'hr.contract.sdi'

    imss_sbc_line_id = fields.Many2one('hr.employee.imss.sbc.line', string="Línea Actualización SBC",
                                        index=True)
