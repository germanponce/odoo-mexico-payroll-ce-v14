# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date


class ResCompany(models.Model):
    _inherit = 'res.company'
        
    hr_employee_nombre = fields.Selection(
        [('1', 'Nombre + Ap. Paterno + Ap. Materno'),
         ('2', 'Ap. Paterno + Ap. Materno + Nombre')],
        string="Orden en Nombre Empleados",
        help="Seleccione la forma en que quiera que se muestren los nombres de los Empleados.",
        default='1')
    
    hr_imss_baja_contrato_y_empleado_archivar = fields.Boolean(
        string="Archivar al confirmar Baja de IMSS", default=True,
        help = "Al confirmar el registro de Baja del IMSS poner "
               "el Contrato en estado Baja y archivar tanto el "
               "Contrato como el Empleado."
    )
    
    hr_imss_vales_despensa_gravado_tomar_gravado_en_bimestre = fields.Boolean(
        string="Cálculo Bimestral - Vale Despensa Gravado en Bimestre", default=True,
        help = "Si está activo entonces al realizar el cálculo de lo Gravado para IMSS "
               "de los Vales de Despensa se calculará tomando en cuenta los días del Bimestre."
               "Si está desactivado entonces se tomará lo Gravado correspondiente al Periodo "
               "de cada Nómina."
    )