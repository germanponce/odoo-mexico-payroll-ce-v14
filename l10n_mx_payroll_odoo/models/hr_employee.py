# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import logging
_logger = logging.getLogger(__name__)

class HREmployee(models.Model):
    _inherit = 'hr.employee'


    curp        = fields.Char(string="CURP", 
                              related="address_home_id.l10n_mx_edi_curp",
                              readonly=False)
