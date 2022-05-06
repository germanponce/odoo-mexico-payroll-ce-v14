# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
import logging
_logger = logging.getLogger(__name__)


class HREmployee(models.Model):
    _inherit ='hr.employee'
    
    
    
    @api.depends('imss_ids', 'imss_ids.state')
    def _get_imss_data(self):
        for rec in self:
            _logger.info("rec.imss_ids: %s" % rec.imss_ids)
            imss_ids = rec.imss_ids and rec.imss_ids or []  #.filtered(lambda w: w.state=='confirm') or []
            rec.update({'last_imss_id' : imss_ids and imss_ids[0].id or False,
                        'prev_imss_id' : imss_ids[1].id if imss_ids and len(imss_ids.ids) > 1 else False})
            
        
    state_of_birth = fields.Many2one('res.country.state', string="Estado de Nacimiento")
    nombre = fields.Char(size=27, string="Nombre", index=True, tracking=True)
    apellido_paterno = fields.Char(size=27, string="Apellido Paterno", index=True, tracking=True)
    apellido_materno = fields.Char(size=27, string="Apellido Materno", index=True, tracking=True)
    clave_subdelegacion = fields.Integer(string="Clave Subdelegación IMSS", index=True, tracking=True,
                                         default=0,
                                         help="Número asignado por la Subdelegación del IMSS")
    unidad_medicina_familiar = fields.Integer(string="Num. Clínica",
                                              help="Unidad de Medicina Familiar o Clínica de Adscripción del Asegurado")
    
    
    last_imss_id = fields.Many2one('hr.employee.imss.line', string="Movimiento IMSS",
                                   compute="_get_imss_data")
    
    prev_imss_id = fields.Many2one('hr.employee.imss.line', string="Previo Movimiento IMSS",
                                   compute="_get_imss_data")
    
    
    imss_ids = fields.One2many('hr.employee.imss.line', 'employee_id', 
                               domain=[('state','=','confirm')],
                               string="Movimientos IMSS", readonly=True)
    
    
    @api.onchange('nombre', 'apellido_paterno', 'apellido_materno')
    def _onchange_nombre_apellidos(self):
        if self.env.user.company_id.hr_employee_nombre == '1':
            self.name = (self.nombre or '') + (self.apellido_paterno and (' ' + self.apellido_paterno) or '') + (self.apellido_materno and (' ' + self.apellido_materno) or '')
        else:
            self.name = (self.apellido_paterno and (self.apellido_paterno or '') +  (self.apellido_materno and (' ' + self.apellido_materno) or '') + ((' ' + self.nombre) or ''))
                
