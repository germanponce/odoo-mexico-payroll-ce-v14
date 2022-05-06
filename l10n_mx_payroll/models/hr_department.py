# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import math
import logging
_logger = logging.getLogger(__name__)


class HRDepartment(models.Model):
    _inherit = 'hr.department'
    
    dia_descanso_variable = fields.Boolean(string="Día de Descanso Variable", default=0,
                                          tracking=True)