# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, tools


class HRPayslipLine(models.Model):
    _inherit = "hr.payslip.line"
    
    imss_gravado = fields.Float(string="IMSS Gravado", digits=(18,2), default=0)
    imss_exento  = fields.Float(string="IMSS Exento", digits=(18,2), default=0)
