# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    
    comedor_monto_descuento_fijo = fields.Boolean(
        related="company_id.comedor_monto_descuento_fijo",
        readonly=False)
    
    comedor_monto_descuento = fields.Monetary(
        related="company_id.comedor_monto_descuento",
        readonly=False)