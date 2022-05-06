# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import logging
_logger = logging.getLogger(__name__)
    

class HRSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    is_dinning_attendance = fields.Boolean(string="Concepto para Comedor")
    
