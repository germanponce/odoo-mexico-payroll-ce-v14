# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
from calendar import monthrange
import base64
import os
import tempfile
import math
import logging
_logger = logging.getLogger(__name__)



class hr_employee_imss_movimientos_sua(models.TransientModel):
    _name = 'hr.employee.imss.movimientos.sua'
    _description = "Asistente para crear Incidencias del IMSS de un mes"
    
    
    state = fields.Selection([('paso1','Parámetros'),
                              ('paso2','Archivos'),
                             ], string="Estado", default='paso1', required=True)
    
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
        
    type = fields.Selection([('08', 'Altas / Reingresos'),
                             ('02', 'Bajas'),
                             ('07', 'Modificaciones'),
                             #('incap', 'Incapacidades'),
                            ], string="Tipo Movimiento", required=True)
    
    
    department_ids = fields.Many2many('hr.department', 'hr_department_movimientos_sua_rel',
                                      'wizard_id', 'department_id',
                                      string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_movimientos_sua_rel',
                                      'wizard_id', 'employee_id',
                                      string="Empleados")
    
    struct_ids = fields.Many2many('hr.payroll.structure', 'hr_payroll_struct_movimientos_sua_rel',
                                 'wizard_id', 'struct_id',
                                 string="Estructuras Salariales")
    
    idse = fields.Binary(string="IDSE", readonly=True)
    idse_filename = fields.Char(string="Archivo IDSE")
    sua_afiliacion = fields.Binary(string="SUA Afiliación", readonly=True)
    sua_afiliacion_filename = fields.Char(string="Archivo SUA Afiliación")
    sua_asegurados = fields.Binary(string="SUA Asegurados", readonly=True)
    sua_asegurados_filename = fields.Char(string="Archivo SUA Asegurados")
    sua_movimientos= fields.Binary(string="SUA Movimientos", readonly=True)
    sua_movimientos_filename = fields.Char(string="Archivo SUA Movimientos")
    
    @api.model
    def default_get(self, default_fields):        
        res = super(hr_employee_imss_movimientos_sua, self).default_get(default_fields)
        today = date.today()
        anterior = today - relativedelta(months=1)
        res.update({'date_from' : date(anterior.year, anterior.month, 1),
                    'date_to'   : date(anterior.year, anterior.month, 
                                       monthrange(anterior.year, anterior.month)[1])
                   })
        return res
  

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
            
    def create_files(self, lines):
        idse = base64.encodestring(self.write_file('\r\n'.join([l.line_idse for l in lines])))
        periodo = 'Del_' + self.date_from.isoformat().replace('-','_') + '_al_' + self.date_to.isoformat().replace('-','_')
        idse_filename = periodo + ('_ALTAS_REINGRESOS_IDSE' if self.type=='08' else '_MODIFICACIONES_IDSE' if self.type=='07' else '_BAJAS_IDSE' if self.type=='02' else '_NO_DEFINIDO') + '.txt'
        
        sua_afiliacion = base64.encodestring(self.write_file('\r\n'.join([l.line_sua_afiliacion for l in lines])))
        sua_afiliacion_filename = periodo + '_SUA_AFILIACION.txt'
        
        sua_asegurados = base64.encodestring(self.write_file('\r\n'.join([l.line_sua_asegurado for l in lines])))
        sua_asegurados_filename = periodo + '_SUA_ASEGURADOS.txt'
        
        sua_movimientos = base64.encodestring(self.write_file('\r\n'.join([l.line_sua_movimiento for l in lines])))
        sua_movimientos_filename = periodo + '_SUA_MOVIMIENTOS.txt'
        
        self.write({'idse' : idse,
                    'idse_filename' : idse_filename,
                    'sua_afiliacion' : sua_afiliacion,
                    'sua_afiliacion_filename' : sua_afiliacion_filename,
                    'sua_asegurados' : sua_asegurados,
                    'sua_asegurados_filename' : sua_asegurados_filename,
                    'sua_movimientos' : sua_movimientos,
                    'sua_movimientos_filename' : sua_movimientos_filename,
        })
        
    
    def get_sua_files(self):
        # Validaciones
        if self.date_from > self.date_to:
            raise ValidationError(_("Error, las fechas están mal definidas."))
        contract_obj = self.env['hr.contract']
        employee_imss_obj = self.env['hr.employee.imss']
        imss_lines_obj = self.env['hr.employee.imss.line']
        
        domain = [('state','=','confirm'), 
                  ('type','=',self.type),
                  ('contract_id.active','in',(True, False))]
        if self.type=='08': # Alta / Reingreso
            domain.append(('fecha_ingreso','>=',self.date_from))
            domain.append(('fecha_ingreso','<=',self.date_to))
        elif self.type=='02': # Bajas
            domain.append(('date_end','>=',self.date_from))
            domain.append(('date_end','<=',self.date_to))
        else: # Modificaciones
            domain.append(('date','>=',self.date_from))
            domain.append(('date','<=',self.date_to))
            
        if self.struct_ids:
            domain.append(('contract_id.struct_id','in',self.struct_ids.ids))
        if self.department_ids:
            domain.append(('contract_id.department_id','in',self.department_ids.ids))
        if self.employee_ids:
            domain.append(('contract_id.employee_id','in',self.employee_ids.ids))
            
    
        lines = imss_lines_obj.search(domain)
        if not lines:
            raise ValidationError(_("No se encontró ningún registro que cumpla con los parámetros dados."))
            
        self.create_files(lines)
        self.write({'state':'paso2'})
        return {'type'      : 'ir.actions.act_window',
                'view_type' : 'form',
                'view_mode' : 'form',
                'res_id'    : self.id,
                'views'     : [(False, 'form')],
                'res_model' : 'hr.employee.imss.movimientos.sua',
                'target'    : 'new',
                }
    
    