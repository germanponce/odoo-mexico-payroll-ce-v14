# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
import base64
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
import os
import tempfile
import logging
_logger = logging.getLogger(__name__)


class HREmployeeIMSS(models.Model):
    _name="hr.employee.imss"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description ="Historial de A/B/M para el IMSS"

    name = fields.Char(string="Referencia", required=True, default='/', index=True,
                      tracking=True)
    
    state   = fields.Selection([('draft', 'Borrador'),
                                ('confirm','Confirmado'),
                                ('cancel', 'Cancelado')
                               ], string="Estado", default='draft',
                               tracking=True,
                               required=True, index=True)
    
    date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True,
                       index=True, tracking=True,
                       states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]})
    
    date_from = fields.Date(
        string='Desde', required=True,
        states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]},
        default=lambda self: fields.Date.to_string(date.today()))
    date_to = fields.Date(
        string='Hasta', required=True,
        states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]},
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(days=-7)).date()))
    
    type = fields.Selection([('08', 'Alta o Reingreso'),
                             ('02','Baja'),
                             ('07', 'Modificación')
                            ], string="Movimiento",
                            required=True, index=True)
    
    
    
    line_ids = fields.One2many('hr.employee.imss.line', 'imss_id',
                               string="Líneas",
                               states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]})
    
    
    idse = fields.Binary(string="Archivo IDSE")
    idse_filename = fields.Char(string="Archivo IDSE.")
    sua_afiliacion = fields.Binary(string="SUA Afiliación")
    sua_afiliacion_filename = fields.Char(string="Archivo SUA Afiliación")
    sua_asegurados = fields.Binary(string="SUA Asegurados")
    sua_asegurados_filename = fields.Char(string="Archivo SUA Asegurados")
    sua_movimientos= fields.Binary(string="SUA Movimientos")
    sua_movimientos_filename = fields.Char(string="Archivo SUA Movimientos")

    
    contract_ids = fields.Many2many('hr.contract', string="Contratos")
    
    company_id          = fields.Many2one('res.company', string='Compañía', 
                                          states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]},
                                          default=lambda self: self.env.user.company_id)
    notes = fields.Text(string="Observaciones",
                        states={'confirm': [('readonly', True)], 'cancel': [('readonly', True)]})
    
    aumento_masivo_id = fields.Many2one('hr.contract.aumento_masivo', 
                                        string="Aumento Masivo", index=True)
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Referencia + Compañía deben ser únicos !'),
        ]

    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            if vals.get('type')=='08': # Altas o Reingresos
                seq = 'hr.employee.imss.alta_reingreso'
            elif vals.get('type')== '02': # Bajas
                seq = 'hr.employee.imss.baja'
            else:
                seq = 'hr.employee.imss.modificacion'
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(seq) or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code(seq) or '/'
        return super(HREmployeeIMSS, self).create(vals)
    
    
    @api.onchange('contract_ids')
    def _onchange_contract_ids(self):
        lines = []
        ids = []
        contract_line_ids = [x.contract_id.id for x in self.line_ids]
        for contract in self.contract_ids:
            if contract.id not in contract_line_ids:
                lines.append((0,0,
                          {'employee_id' : contract.employee_id.id,
                           'cfdi_sueldo_base' : contract.cfdi_salario_diario_integrado2 or contract.cfdi_salario_diario_integrado,
                           'contract_id' : contract._origin.id,
                           'causa_baja' : '2',
                          }))
        self.line_ids = lines
            

            
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
        idse_filename = self.date.isoformat() + ('_ALTAS_REINGRESOS_IDSE' if self.type=='08' else '_MODIFICACIONES_IDSE' if self.type=='07' else '_BAJAS_IDSE' if self.type=='02' else '_NO_DEFINIDO') + '.txt'
        
        sua_afiliacion = base64.encodestring(self.write_file('\n'.join([l.line_sua_afiliacion for l in self.line_ids])))
        sua_afiliacion_filename = self.date.isoformat() + '_SUA_AFILIACION.txt'
        
        sua_asegurados = base64.encodestring(self.write_file('\n'.join([l.line_sua_asegurado for l in self.line_ids])))
        sua_asegurados_filename = self.date.isoformat() + '_SUA_ASEGURADOS.txt'
        
        sua_movimientos = base64.encodestring(self.write_file('\n'.join([l.line_sua_movimiento for l in self.line_ids])))
        sua_movimientos_filename = self.date.isoformat() + '_SUA_MOVIMIENTOS.txt'
        
        self.write({'idse' : idse,
                    'idse_filename' : idse_filename,
                    'sua_afiliacion' : sua_afiliacion,
                    'sua_afiliacion_filename' : sua_afiliacion_filename,
                    'sua_asegurados' : sua_asegurados,
                    'sua_asegurados_filename' : sua_asegurados_filename,
                    'sua_movimientos' : sua_movimientos,
                    'sua_movimientos_filename' : sua_movimientos_filename,
        })
        return True
            
    
    def action_confirm(self):
        context = self._context and dict(self._context.copy()) or {}
        for rec in self:
            contracts = self.env['hr.contract'].browse([])
            employees = self.env['hr.employee'].browse([])
            for line in rec.line_ids:
                # Validaciones IDSE
                if line.employee_id.last_imss_id.type=='02' and rec.type=='02':
                    raise ValidationError(_('Error!\nNo puede generar una baja para el Empleado %s porque ya se encuentra dado de Baja. Por favor revise.') % line.employee_id.name)
                elif context.get('script', True) and line.employee_id.last_imss_id.type=='02' and rec.type=='07':
                    raise ValidationError(_('Error!\nNo puede generar una Modificación del Empleado %s porque se encuentra dado de Baja. En su lugar debe generar una Alta/Reingreso.  Por favor revise.') % line.employee_id.name)
                elif line.employee_id.last_imss_id.type=='08' and rec.type=='08':
                    raise ValidationError(_('Error!\nNo puede generar una Alta del Empleado %s porque el Movimiento anterior fue una Alta. En su lugar debe generar una Modificación.  Por favor revise.') % line.employee_id.name)
                
                if rec.type=='02': # Baja
                    contracts += line.contract_id
                    employees += line.employee_id
            if rec.type=='02' and contracts: # Baja
                contracts.write({'state':'baja', 'active':0})
                employees.write({'active':0})
            rec.create_files()
        self.write({'state':'confirm'})
            
    
    def action_cancel(self):
        return self.write({'state':'cancel',
                          'idse'    : False,
                          'idse_filename' : False,
                          'sua_afiliacion': False,
                          'sua_afiliacion_filename' : False,
                          'sua_asegurados' : False,
                          'sua_asegurados_filename' : False,
                          'sua_movimientos' : False,
                          'sua_movimientos_filename' : False})
    
            
class HREmployeeIMSSLine(models.Model):
    _name="hr.employee.imss.line"
    _description ="Líneas de Historial del Empleado para el IMSS"
    _order = 'date desc, name desc'
      
    def get_idse_line(self):
        if self.type in ('08','07'): # Alta o Reingreso / Modificacion
            return '%s%s%s%s%s%s      %s%s%s%s%s%s%s%s %s9' % \
                    (self.company_id.registro_patronal,
                     self.employee_id.nss,
                     self.employee_id.apellido_paterno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                     self.employee_id.apellido_materno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27] if self.employee_id.apellido_materno else (' '*27),
                     self.employee_id.nombre.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                     '{:07.2f}'.format(self.contract_id.cfdi_salario_diario_integrado2 or self.contract_id.cfdi_salario_diario_integrado).replace('.',''),
                     
                     self.contract_id.tipo_trabajador,
                     self.contract_id.tipo_salario,
                     self.contract_id.jornada_reducida,
                     (self.contract_id.date_start if self.type=='07' else self.contract_id.fecha_ingreso).strftime('%d%m%Y'),
                     ('{:03}'.format(self.employee_id.unidad_medicina_familiar) + '  ') if self.type=='08' else (' '*5),
                     self.type,
                     '{:05}'.format(self.employee_id.clave_subdelegacion),
                     self.employee_id.num_empleado.ljust(10, ' ')[:10],
                     self.employee_id.curp
                    )
            #1122334455611223344556Cruz                       Argil                      Israel                     0      1000123  08004061234567891 9

        else: # Baja
            return '%s%s%s%s%s000000000000000%s     %s%s%s%s%s9' % \
                    (self.company_id.registro_patronal,
                     self.employee_id.nss,
                     self.employee_id.apellido_paterno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                     self.employee_id.apellido_materno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27], 
                     self.employee_id.nombre.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                     self.contract_id.date_end.strftime('%d%m%Y'),
                     self.type,
                     '{:05}'.format(self.employee_id.clave_subdelegacion),
                     self.employee_id.num_empleado.ljust(10, ' ')[:10],
                     self.causa_baja,
                     (' ' * 18)
                    )
    
    def get_sua_line(self):
        
        if not self.employee_id.address_home_id.zip or len(self.employee_id.address_home_id.zip.replace(' ','').replace('.','')) != 5:
            raise ValidationError(_('Error !\nEl código postal de la dirección del Trabajador %s no está capturado correctamente') % self.employee_id.name)
        if not self.employee_id.birthday:
            raise ValidationError(_('Error !\nLa fecha de nacimiento del Trabajador %s no está capturada') % self.employee_id.name)
        if not self.employee_id.state_of_birth or self.employee_id.state_of_birth.country_id.code!='MX':
            raise ValidationError(_('Error !\nEl Estado de nacimiento del Trabajador %s no está capturado o el Estado no corresponde al País de México)') % self.employee_id.name)    
        if self.employee_id.gender not in ('male','female'):
            raise ValidationError(_('Error !\nEl género del Trabajador %s no está capturado correctamente') % self.employee_id.gender)
        
        # Datos infonavit
        tipo_descuento_infonavit = {'porcentaje': '1',
                                    'importe'   : '2',
                                    'veces_umi' : '3'}
        factor_infonavit = ''
        if self.employee_id.infonavit_ids:
            factor = self.employee_id.infonavit_ids[0].factor
            if self.employee_id.infonavit_ids[0].tipo == 'porcentaje':
                factor_infonavit = '{:08.2f}'.format(factor).replace('.','') + '0'    
            elif self.employee_id.infonavit_ids[0].tipo == 'importe':
                factor_infonavit = '{:07.2f}'.format(factor).replace('.','') + '00'
            elif self.employee_id.infonavit_ids[0].tipo == 'veces_umi':
                factor_infonavit = '{:09.4f}'.format(factor).replace('.','')
        
        l_sua_afiliacion = '%s%s%s%s%s%s%s%s%s%s ' % \
                (self.company_id.registro_patronal,
                 self.employee_id.nss,
                 self.employee_id.address_home_id.zip,
                 self.employee_id.birthday.strftime('%d%m%Y'),
                 self.employee_id.place_of_birth.ljust(25, ' ')[:25],
                 self.employee_id.state_of_birth.imss_code,
                 '{:03}'.format(self.employee_id.unidad_medicina_familiar),
                 self.employee_id.contract_id.job_id and self.employee_id.contract_id.job_id.name.ljust(12, ' ')[:12] or (' '*12),
                 'M' if self.employee_id.gender=='male' else 'F',
                 self.contract_id.tipo_salario
                )

        l_sua_movimiento = '%s%s%s%s        00%s' % \
                (self.company_id.registro_patronal,
                 self.employee_id.nss,
                 self.type,
                 (self.contract_id.date_start if self.type=='07' else self.contract_id.fecha_ingreso if self.type=='08' else self.contract_id.date_end).strftime('%d%m%Y'),
                 '{:06.2f}'.format(self.contract_id.cfdi_salario_diario_integrado2 or self.contract_id.cfdi_salario_diario_integrado).replace('.','')
                )
            
        l_sua_asegurado = '%s%s%s%s%s%s%s%s%s%s%s%s%s' % \
                (self.company_id.registro_patronal,
                 self.employee_id.nss,
                 self.employee_id.address_home_id.vat,
                 self.employee_id.curp or self.employee_id.address_home_id.curp,
                 (self.employee_id.apellido_paterno + '$' + (self.employee_id.apellido_materno and self.employee_id.apellido_materno.replace('ñ','n').replace('Ñ','N') or '')  + '$' +  self.employee_id.nombre).ljust(50, ' ')[:50],
                 self.contract_id.tipo_trabajador, # Tipo de Trabajador
                 self.contract_id.jornada_reducida, # Jornada Reducida
                 self.contract_id.fecha_ingreso.strftime('%d%m%Y'), # Fecha Alta
                 '{:08.2f}'.format(self.contract_id.cfdi_salario_diario_integrado2 or self.contract_id.cfdi_salario_diario_integrado).replace('.',''),
                 self.contract_id.department_id.name.ljust(17, ' ')[:17],
                 self.employee_id.infonavit_ids and self.employee_id.infonavit_ids[0].name.ljust(10, ' ')[:10] or '0000000000',
                 self.employee_id.infonavit_ids and tipo_descuento_infonavit[self.employee_id.infonavit_ids[0].tipo] or '',
                 factor_infonavit
                )
        return l_sua_afiliacion, l_sua_movimiento, l_sua_asegurado
             
    
    @api.depends('employee_id', 'contract_id')
    def _get_line(self):
        for l in self:
            # Validaciones IDSE
            if not l.imss_id.company_id.registro_patronal or len(l.imss_id.company_id.registro_patronal) != 11:
                raise ValidationError(_('Error !\nEl Registro patronal de la Empresa está mal definido, por favor revise'))
            if not l.employee_id.nss or len(l.employee_id.nss) != 11:
                raise ValidationError(_('Error !\nEl Número de Seguro Social del Trabajador %s no tiene 11 caracteres') % l.employee_id.name)
            if not l.cfdi_sueldo_base or l.cfdi_sueldo_base < 0:
                raise ValidationError(_('Error !\nEl SDI del Trabajador %s no puede ser igual o menor a cero') % l.employee_id.name)
            if l.type=='08' and not l.contract_id.tipo_trabajador:
                raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Trabajador para %s') % l.employee_id.name)
            if l.type in ('07','08'):
                if not l.contract_id.tipo_salario:
                    raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Salario para %s') % l.employee_id.name)
                if not l.contract_id.jornada_reducida:
                    raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Jornada para %s') % l.employee_id.name)
                if not l.employee_id.curp:
                    raise ValidationError(_('Error !\nNo está definido la CURP para %s') % l.employee_id.name)
                if len(l.employee_id.curp) !=18:
                    raise ValidationError(_('Error !\nLa CURP para %s no contiene 18 caracteres') % l.employee_id.name)
            
            l.line_idse = l.get_idse_line()
            l.line_sua_afiliacion, l.line_sua_movimiento, l.line_sua_asegurado = l.get_sua_line()
    
    
    imss_id = fields.Many2one('hr.employee.imss', string="Movimiento",
                             required=True, ondelete='cascade')
    name = fields.Char(related='imss_id.name', store=True)
    date = fields.Date(related='imss_id.date', store=True, index=True)
    state = fields.Selection(related='imss_id.state', store=True, index=True)
    
    employee_id = fields.Many2one('hr.employee', string="Trabajador",
                                  required=True, index=True)
    
    type = fields.Selection(related="imss_id.type", store=True, string="Tipo Movimiento")
    
    causa_baja = fields.Selection([('0', 'No aplica'),
                                   ('1', 'Término de Contrato'),
                                   ('2', 'Separación Voluntaria'),
                                   ('3', 'Abandono de Empleo'),
                                   ('4', 'Defunción'),
                                   ('5', 'Clausura'),
                                   ('6', 'Otras'),
                                   ('7', 'Ausentismo'),
                                   ('8', 'Rescisión de Contrato'),
                                   ('9', 'Jubilación'),
                                   ('A', 'Pensión')],
                                 string="Causa de Baja",
                                 default='0', index=True)
    
    cfdi_sueldo_base = fields.Float(string="SBC", default=0,
                                   readonly=False)
    
    contract_id = fields.Many2one('hr.contract', string="Contrato")
    fecha_ingreso = fields.Date(related="contract_id.fecha_ingreso", 
                                readonly=True, store=True, index=True)
    department_id = fields.Many2one('hr.department', related="contract_id.department_id",
                                    string="Departamento", store=True)
    date_start = fields.Date(string="Inicio Contrato", related="contract_id.date_start", 
                             readonly=True, store=True, index=True)
    date_end = fields.Date(string ="Fin Contrato", related="contract_id.date_end", 
                           readonly=True, store=True, index=True)
    
    tipo_salario = fields.Selection(related="contract_id.tipo_salario")
    tipo_trabajador = fields.Selection(related="contract_id.tipo_trabajador")
    jornada_reducida = fields.Selection(related="contract_id.jornada_reducida")
    line_idse = fields.Text(string="Línea TXT IDSE", compute="_get_line")
    line_sua_afiliacion = fields.Text(string="Línea TXT SUA Afiliación", compute="_get_line")
    line_sua_movimiento = fields.Text(string="Línea TXT SUA Movimiento", compute="_get_line")
    line_sua_asegurado  = fields.Text(string="Línea TXT SUA Asegurado", compute="_get_line")
    
    company_id          = fields.Many2one('res.company', related="imss_id.company_id")
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.contract_id = self.employee_id.contract_id.id
        

class HRContractAumentoMasivo(models.Model):
    _inherit = 'hr.contract.aumento_masivo'
    
    def action_confirm(self):
        res = super(HRContractAumentoMasivo, self).action_confirm()
        self.create_imss_record()
        return res
        
    def create_imss_record(self):
        imss_obj = self.env['hr.employee.imss']
        
        contract_ids = [l.new_contract_id.id for l in self.line_ids.filtered(lambda w: w.aplicar_aumento)]
        data ={'date'       : self.date,
               'date_from'  : self.date,
               'date_to'    : self.date,
               'type'       : '07',
               'contract_ids' : contract_ids,
               'notes'      : _('Registro creado desde Actualización Bimestral de SBC %s' % self.name)
              }
        imss_rec = imss_obj.new(data)
        imss_rec._onchange_contract_ids()
        data_modif = imss_rec._convert_to_write(imss_rec._cache)
        imss_id = imss_obj.create(data_modif)
        imss_id.action_confirm()
        
        
    def action_cancel(self):
        res = super(HRContractAumentoMasivo, self).action_cancel()
        imss_rec = self.env['hr.employee.imss'].search([('aumento_masivo_id','=', self.id)])
        imss_rec.action_cancel()
        return res