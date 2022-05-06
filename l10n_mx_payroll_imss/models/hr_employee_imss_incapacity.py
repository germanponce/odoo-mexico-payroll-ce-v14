# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
import base64
import os
import tempfile
import logging
_logger = logging.getLogger(__name__)


class HREmployeeIMSSIncapacity(models.Model):
    _name="hr.employee.imss.incapacity"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description ="Incapacidades IMSS"
    
    name = fields.Char(string="Referencia", default='/', required=True, index=True)
    
    date = fields.Date(string="Fecha", required=True,
                       tracking=True, index=True,
                       default=fields.Date.context_today,
                       readonly=True, states={'draft': [('readonly', False)]})
    
    state   = fields.Selection([('draft', 'Borrador'),
                                ('confirm','Confirmado'),
                                ('cancel', 'Cancelado')
                               ], string="Estado", default='draft',
                               tracking=True,
                               required=True, index=True)
    
    line_ids = fields.One2many('hr.employee.imss.incapacity.line', 'incapacity_id',
                              string="Líneas", readonly=True)
    
    idse = fields.Binary(string="Archivo IDSE", readonly=True)
    idse_filename = fields.Char(string="IDSE Filename")
    sua_datos = fields.Binary(string="SUA Datos", readonly=True)
    sua_datos_filename = fields.Char(string="Archivo SUA Datos")
    sua_movimientos= fields.Binary(string="SUA Movimientos", readonly=True)
    sua_movimientos_filename = fields.Char(string="Archivo SUA Movimientos")
    
    company_id = fields.Many2one('res.company', string='Compañía', 
                                 default=lambda self: self.env.user.company_id)
    
    notes = fields.Text(string="Observaciones",
                        readonly=True, states={'draft': [('readonly', False)]})
    
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Referencia + Compañía deben ser únicos !'),
        ]
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            seq = 'hr.employee.imss.incapacity'
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(seq) or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code(seq) or '/'
        return super(HREmployeeIMSSIncapacity, self).create(vals)
    
    
    
    def write_file(self, content):
        (fileno, fname) = tempfile.mkstemp('.txt', 'tmp')
        os.close(fileno)
        f_write = open(fname, 'w')
        f_write.write(content)
        f_write.close()
        f_read = open(fname, "rb")
        fdata = f_read.read()
        f_read.close()
        return fdata
            
    def create_files(self):
        idse = base64.encodestring(self.write_file('\n'.join([l.line_idse for l in self.line_ids])))
        idse_filename = 'INCAPACIDADES_IDSE_' + self.date.isoformat().replace('-','_') +  '.txt'
        
        sua_datos = base64.encodestring(self.write_file('\n'.join([l.line_sua_datos for l in self.line_ids])))
        sua_datos_filename = 'Incap_Dat_SUA_al_' + self.date.isoformat().replace('-','_') + '.txt'
        
        sua_movimientos = base64.encodestring(self.write_file('\n'.join([l.line_sua_movimientos for l in self.line_ids])))
        sua_movimientos_filename = 'Incap_Mov_SUA_al_' + self.date.isoformat().replace('-','_') + '.txt'
        
        self.write({'idse' : idse,
                    'idse_filename' : idse_filename,
                    'sua_datos' : sua_datos,
                    'sua_datos_filename' : sua_datos_filename,
                    'sua_movimientos' : sua_movimientos,
                    'sua_movimientos_filename' : sua_movimientos_filename,
        })
        return True
            
    
    def action_confirm(self):
        for rec in self:
            rec.create_files()
        self.write({'state':'confirm'})
            
    
    def action_cancel(self):
        return self.write({'state':'cancel',
                          'idse'    : False,
                          'idse_filename' : False,
                          'sua_datos': False,
                          'sua_datos_filename' : False,
                          'sua_movimientos' : False,
                          'sua_movimientos_filename' : False})

class HREmployeeIMSSIncapacityLine(models.Model):
    _name="hr.employee.imss.incapacity.line"
    _description ="Incapacidades IMSS - Lineas"
    
    def get_idse_line(self):
        return '%s%s' % \
                (self.leave_id.company_id.registro_patronal,
                 self.employee_id.nss
                )
    
    def get_sua_line(self):

        l_sua_datos = '%s%s%s%s%s%s%s%s%s%s%s%s' % \
                (self.leave_id.company_id.registro_patronal,
                 self.employee_id.nss,
                 '0', # Segun debe ser 1, pero en el archivo de ejemplo maneja 0
                 self.date_from.strftime('%d%m%Y'),
                 self.leave_id.incapacidad_folio, # 8 posiciones
                 '{:03}'.format(int(self.number_of_days)), # Num dias "subsidiados"
                 '{:03}'.format(self.leave_id.incapacidad_porcentaje), # Porcentaje Incapacidad
                 str(int(self.leave_id.tipoincapacidad_id.code)), # Rama de Incapacidad
                 self.leave_id.incapacidad_tipo_riesgo, # Tipo de Riesgo
                 self.leave_id.incapacidad_secuela, # Secuela Incapacidad
                 self.leave_id.incapacidad_control,  # Control Incapacidad
                 self.date_to.strftime('%d%m%Y')
                )
        
        l_sua_movimientos = '%s%s%s%s%s%s%s%s' % \
                (self.leave_id.company_id.registro_patronal,
                 self.employee_id.nss,
                 str(int(self.leave_id.tipoincapacidad_id.code)), # Rama de Incapacidad
                 self.leave_id.incapacidad_control,  # Control Incapacidad
                 self.date_from.strftime('%d%m%Y'),
                 self.leave_id.incapacidad_folio, # 8 posiciones
                 '{:02}'.format(int(self.number_of_days)), # Num dias "subsidiados"
                 '0000000'
                )
        
        return l_sua_datos, l_sua_movimientos
            
    
    @api.depends('employee_id', 'contract_id')
    def _get_line(self):
        for l in self:
            # Validaciones IDSE
            if not l.leave_id.company_id.registro_patronal or len(l.leave_id.company_id.registro_patronal) != 11:
                raise ValidationError(_('Error !\nEl Registro patronal de la Empresa está mal definido, por favor revise'))
            if not l.employee_id.nss or len(l.employee_id.nss) != 11:
                raise ValidationError(_('Error !\nEl Número de Seguro Social del Trabajador %s no tiene 11 caracteres') % l.employee_id.name)
            
            l.line_idse = l.get_idse_line()
            l.line_sua_datos, l.line_sua_movimientos = l.get_sua_line()
            
    line_idse = fields.Text(string="Línea TXT IDSE", compute="_get_line")
    line_sua_datos = fields.Text(string="Línea TXT Datos", compute="_get_line")
    line_sua_movimientos = fields.Text(string="Línea TXT Movimientos", compute="_get_line")
    
    incapacity_id = fields.Many2one('hr.employee.imss.incapacity', string="Incapacidad", required=True,
                                  index=True, readonly=True)
    
    leave_id = fields.Many2one('hr.leave', string="Ausencia", required=True,
                               index=True, readonly=True)
    
    number_of_days = fields.Float(string="# Días", related="leave_id.number_of_days_display",
                                    readonly=True, store=True)
    
    date_from = fields.Date(string="Desde", related='leave_id.request_date_from', 
                            readonly=True, store=True)
    
    date_to   = fields.Date(string="Hasta", related='leave_id.request_date_to', 
                            readonly=True, store=True)
        
    employee_id = fields.Many2one('hr.employee', string="Empleado", 
                                  related='leave_id.employee_id', 
                                  readonly=True, store=True)
    
    contract_id = fields.Many2one('hr.contract', string="Contrato", 
                                  related='leave_id.contract_id', 
                                  readonly=True, store=True)
    
    leave_type_id = fields.Many2one('hr.leave.type', string="Tipo Ausencia", 
                            related='leave_id.holiday_status_id',
                            readonly=True, store=True)
    
    tipoincapacidad_id = fields.Many2one('sat.nomina.tipoincapacidad', string="Tipo Incapacidad", 
                                         related='leave_type_id.tipoincapacidad_id',
                                         readonly=True, store=True)
    
