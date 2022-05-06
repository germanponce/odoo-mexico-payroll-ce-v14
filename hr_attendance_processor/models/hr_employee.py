# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import logging
_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    no_revisar_asistencia = fields.Boolean(string="No revisar Asistencia",
                                          default=False, index=True,
                                          help="Al activar la casilla entonces el Procesador de Asistencias "
                                               "ignorará este empleado.")
