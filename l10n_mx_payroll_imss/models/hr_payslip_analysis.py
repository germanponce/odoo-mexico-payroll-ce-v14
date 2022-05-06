# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
import logging
_logger = logging.getLogger(__name__)


class hr_payslip_analysis(models.Model):
    _inherit = "hr.payslip.analysis"
    
    imss_gravado = fields.Float(string="IMSS Gravado", readonly=True)
    imss_exento = fields.Float(string="IMSS Exento", readonly=True)
    
    
    def query_select(self):
        res = super(hr_payslip_analysis, self).query_select()
        return res + ", l.imss_gravado, l.imss_exento"
