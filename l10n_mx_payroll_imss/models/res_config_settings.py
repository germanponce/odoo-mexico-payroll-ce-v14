# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    
    hr_employee_nombre = fields.Selection(related='company_id.hr_employee_nombre',
                                          readonly=False)

    hr_imss_baja_contrato_y_empleado_archivar = fields.Boolean(
        related='company_id.hr_imss_baja_contrato_y_empleado_archivar', readonly=False
    )
    
    hr_imss_vales_despensa_gravado_tomar_gravado_en_bimestre = fields.Boolean(
        related='company_id.hr_imss_vales_despensa_gravado_tomar_gravado_en_bimestre',
        readonly=False
    )