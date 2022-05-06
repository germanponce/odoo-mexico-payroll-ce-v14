# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
import logging
_logger = logging.getLogger(__name__)


class HRSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    aplica_calculo_imss = fields.Boolean(string="Cálculo IMSS", default=0, tracking=True)
    
    python_code_imss    = fields.Text(string="Código Python IMSS", tracking=True,
                                     default="""
                                     ### slip - Para referirse a la nomina que se esta procesando
                                     ### line - Para referirse a la linea de la nomina que se esta procesando
                                     ### _logger
                                     """)