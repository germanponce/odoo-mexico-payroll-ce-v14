# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date


class ResCompany(models.Model):
    _inherit = 'res.company'

    comedor_monto_descuento_fijo = fields.Boolean(
        string="Monto de Comedor es fijo",
        default=True,
        help="Parámetro para indicar si el descuento por comedor es por un monto fijo o variable.\n"
        "Si lo desactiva podrá indicar el monto a descontar del trabajador al momento de capturar \n"
        "el registro de Comedor")
    
    comedor_monto_descuento = fields.Monetary(
        string="Monto descuento comedor",
        default=0,
        help="Aquí puede definir el monto a descontar por cada registro \n"
        "de asistencia al comedor"
    )