# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from odoo.addons import decimal_precision as dp

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    
    crear_faltas_x_acumulacion_retardos = fields.Boolean(
        string="Crear Faltas por Acumulación de Retardos", default=True)
    
    aplica_descuento_x_minuto_retardo =  fields.Boolean(
        string="Crear Descuento por Minuto de Retardo", default=True)
