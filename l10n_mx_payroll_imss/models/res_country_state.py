# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date


class ResCountryState(models.Model):
    _inherit = 'res.country.state'
    
    imss_code = fields.Char(string="Código Estado IMSS")