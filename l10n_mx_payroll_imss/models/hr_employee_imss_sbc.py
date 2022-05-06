# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
import base64
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import calendar
import math
import pytz
import os
import tempfile
import logging
_logger = logging.getLogger(__name__)


    
class HREmployeeIMSSSSBC(models.Model):
    _name="hr.employee.imss.sbc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description ="Actualizacion bimestral del SBC para IMSS"
    
    
    @api.depends('date_from', 'date_to')
    def _get_dias_base(self):
        for rec in self:
            rec.dias_base = (rec.date_to - rec.date_from).days + 1
    
    @api.depends('line_ids')
    def _compute_lines(self):
        for rec in self:
            rec.count_lines = len(rec.line_ids.ids)
            
    count_lines = fields.Integer(string="Líneas", compute="_compute_lines")
    
    name = fields.Char(string="Referencia", required=True, default="/", index=True,
                      tracking=True, readonly=True)
    
    date = fields.Date(string="Fecha Aplicación", 
                       default=fields.Date.context_today, required=True,
                       index=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    
    date_from = fields.Date(string="Fecha Inicial", 
                       default=fields.Date.context_today, required=True,
                       index=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    
    date_to = fields.Date(string="Fecha Final", 
                       default=fields.Date.context_today, required=True,
                       index=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    
    dias_base = fields.Integer(string="Días Bimestre", compute="_get_dias_base", store=True)
    
    lugar_de_trabajo = fields.Char(string="Lugares de Trabajo",
                                   help="Puede especificar varios lugares de trabajo separados por comas, note que no debe dejar espacios entre las comas.",
                                   readonly=True, states={'draft': [('readonly', False)]})
                                  
    department_ids = fields.Many2many('hr.department', string="Departamentos",
                                      help="Puede filtrar los contratos por departamento(s)",
                                      readonly=True, states={'draft': [('readonly', False)]})
    
    contract_ids = fields.Many2many('hr.contract', string="Contratos",
                                    readonly=True, states={'draft': [('readonly', False)]})
    
    contract_filter_ids = fields.Many2many('hr.contract', 
                                           'imss_sbc_contract_filter_rel',
                                           'imss_sbc_id', 'contract_id',
                                           string="Contratos a Filtrar",
                                           readonly=True, states={'draft': [('readonly', False)]})
    
    
    state   = fields.Selection([('draft', 'Borrador'),
                                ('confirm','Confirmado'),
                                ('cancel', 'Cancelado')
                               ], string="Estado", default='draft',
                               tracking=True,
                               required=True, index=True)
    
    uma_id             = fields.Many2one('sat.nomina.uma_umi', string='·UMA', 
                                      readonly=True,
                                      states={'draft': [('readonly', False)]})
    
    line_ids = fields.One2many('hr.employee.imss.sbc.line', 'imss_sbc_id',
                              readonly=True, states={'draft': [('readonly', False)]})
    
    notes = fields.Text(string="Observaciones",
                        readonly=True, states={'draft': [('readonly', False)]})
                       
    company_id          = fields.Many2one('res.company', string='Compañía', 
                                          default=lambda self: self.env.user.company_id)
    
    salary_rule_ids = fields.Many2many(
        'hr.salary.rule', string="Reglas Salariales (Percepciones Variables)",
        domain=[('tipopercepcion_id','!=',False),('nomina_aplicacion','=','percepcion')],
        readonly=True, states={'draft': [('readonly', False)]})
    
    idse = fields.Binary(string="Archivo", readonly=True)
    idse_filename = fields.Char(string="Archivo IDSE")
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Referencia + Compañía deben ser únicos !'),
        ]
    
    @api.model
    def default_get(self, default_fields):
        res = super(HREmployeeIMSSSSBC, self).default_get(default_fields)
        record_ids =  self._context.get('active_ids',[])
        
        ##### TIPO DE INGRESOS #####
        # 010	Premios por puntualidad
        # 014	Subsidios por incapacidad
        # 019	Horas extra
        # 020	Prima dominical
        # 028	Comisiones
        # 029	Vales de despensa
        # 030	Vales de restaurante
        # 031	Vales de gasolina
        # 032	Vales de ropa
        # 033	Ayuda para renta
        # 034	Ayuda para artículos escolares
        # 035	Ayuda para anteojos
        # 036	Ayuda para transporte
        # 038	Otros ingresos por salarios
        # 045	Ingresos en acciones o títulos valor que representan bienes
        # 047	Alimentación
        # 048	Habitación
        # 049	Premios por asistencia
        ##########
        salary_rule_ids = self.env['hr.salary.rule'].search([('tipopercepcion_id','!=',False),
                                                             ('nomina_aplicacion','=','percepcion'),
                                                             ('tipopercepcion_id.code','in',('010', '014', '019', '020', '028', '029', '030', '031', '032', '033', '034', '035', '036', '038', '045', '047', '048', '049'))])
        
        uma = self.env['sat.nomina.uma_umi'].search([('tipo','=','uma')],order='vigencia desc', limit=1)
        
        res.update({'salary_rule_ids'    : salary_rule_ids.ids,
                    'uma_id' : uma and uma.id or False,
                   })
        return res
    
    
    @api.onchange('date_to')
    def _onchange_date_to(self):
        self.date = self.date_to + timedelta(days=1)
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            seq = 'hr.employee.imss.sbc'
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(seq) or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code(seq) or '/'
        return super(HREmployeeIMSSSSBC, self).create(vals)
    
    
    def action_compute(self):
        self.ensure_one()
        dias_base = self.dias_base
        contract_obj = self.env['hr.contract']
        holiday_obj = self.env['hr.leave']
        payslip_line_obj = self.env['hr.payslip.line']
        extra_obj = self.env['hr.payslip.extra']
        salary_rule_obj = self.env['hr.salary.rule']
        presta_obj = self.env['sat.nomina.tabla_prestaciones']
        tabla_vac_obj = self.env['sat.nomina.tabla_vacaciones']
        imss_sbc_obj = self.env['hr.employee.imss.sbc.line']
        param_vales_despensa = self.env.company.hr_imss_vales_despensa_gravado_tomar_gravado_en_bimestre
        vale_despensa = salary_rule_obj.search([('nomina_aplicacion','=','percepcion'),
                                                ('tipopercepcion_id.code','=','029')],
                                               limit=1)
        if not vale_despensa:
            raise ValidationError(_("No se encontró la Regla Salarial para Vales de Despensa"))
        vale_despensa_id = vale_despensa.id
        if self.contract_ids:
            contract_ids = self.contract_ids
        else:
            domain = [('employee_id','!=',False)]
            contract_ids = contract_obj.browse([])
            if self.department_ids:
                domain.append(('department_id','in',self.department_ids.ids))
            if self.lugar_de_trabajo:
                domain.append(('employee_id.work_location','in',(self.lugar_de_trabajo.split(','))))

            domain2 = domain
            domain2.append(('state','in',('open','pending')))
            contract_ids1 = contract_obj.search(domain2)
            contract_ids += contract_ids1
            
            employee_ids = [c.employee_id.id for c in contract_ids1]
            
            domain += [('state','=','close'),
                       ('date_end','>=',self.date_from),
                       ('date_end','<',self.date)]
            contract_ids2 = contract_obj.search(domain)
            if contract_ids2:
                contract_ids_x = contract_ids2.filtered(lambda w: w.id not in contract_ids1.ids and \
                                                                  w.employee_id.id not in employee_ids)
                if contract_ids_x:
                    contract_ids += contract_ids_x 
        
        
        #raise ValidationError("Pausa")
        self.line_ids.unlink()
        lines = []
        if not self.contract_ids:
            self.contract_ids = contract_ids
        employee_ids = [c.employee_id.id for c in contract_ids]
        incapacidades_recs = extra_obj.read_group([
                ('employee_id','in', employee_ids),
                ('date', '>=', self.date_from),
                ('date','<=',self.date_to),
                ('state','in',('approved','done')),
                ('leave_id','!=',False),
                ('leave_id.es_incapacidad','=',True)
            ], ['qty'], ['employee_id'])
        
        
        incapacidades = {}
        for _w in incapacidades_recs:
            incapacidades[_w['employee_id'][0]] = _w['qty']
                
        faltas_recs = extra_obj.read_group([
                ('employee_id','in', employee_ids),
                ('date', '>=', self.date_from),
                ('date','<=',self.date_to),
                ('state','in',('approved','done')),
                ('leave_id','!=',False),
                ('leave_id.es_incapacidad','!=',True),
                ('leave_id.holiday_status_id.unpaid','=','True'),
            ], ['qty'], ['employee_id'])
        
        faltas = {}
        for _w in faltas_recs:
            faltas[_w['employee_id'][0]] = _w['qty']

        employees = []
        for contract in contract_ids:
            _logger.info("===============")
            _logger.info("** %s - %s**" % (contract.employee_id.name, contract.name))
            _logger.info("===============")

            if contract.employee_id.id in employees:
                _logger.info("No se hace nada...")
                continue
            employees.append(contract.employee_id.id)
            data = {'contract_id' : contract.id}
            imss_ids = contract.employee_id.imss_ids.filtered(lambda w: w.type=='08')
            fecha_alta = contract.fecha_ingreso
            
            antig_laboral = ((self.date - fecha_alta).days + 1.0) / 365.25
            holidays = holiday_obj.search([('employee_id','=', contract.employee_id.id),
                                           ('date_from', '<=', self.date), #tz.localize(horario_entrada).astimezone(pytz.utc)),
                                           ('date_to','>=',self.date), #tz.localize(horario_salida).astimezone(pytz.utc)),
                                           ('state','=','validate'),
                                          ])

            incapacitado_en_fecha_aplicacion = bool(holidays)
            
            data.update({'fecha_alta'   : fecha_alta,
                         'antig_laboral': antig_laboral,
                        'incapacitado_en_fecha_aplicacion' : incapacitado_en_fecha_aplicacion,
                        'aplicar_modificacion_sbc' : not incapacitado_en_fecha_aplicacion})

            prestacion = presta_obj.search([('sindicalizado','=',contract.sindicalizado),
                                            ('antiguedad','=',math.ceil(antig_laboral))], limit=1)
            
            if prestacion:            
                dias_vacaciones = prestacion.dias_vacaciones
                dias_aguinaldo = prestacion.dias_aguinaldo
                porc_prima_vacacional = prestacion.prima_vacacional
            else:                
                dias_aguinaldo = 15.0
                vacaciones = tabla_vac_obj.search([('antiguedad','=',math.ceil(antig_laboral))],limit=1)
                dias_vacaciones = vacaciones and vacaciones.dias or 0
                porc_prima_vacacional = 25.0
            #_logger.info("dias_vacaciones: %s" % dias_vacaciones)
            #_logger.info("dias_aguinaldo: %s" % dias_aguinaldo)
            #_logger.info("porc_prima_vacacional: %s" % porc_prima_vacacional)
            
            aguinaldo = contract.cfdi_sueldo_base * dias_aguinaldo / 365.0 * self.dias_base
            prima_vacacional = (contract.cfdi_sueldo_base * dias_vacaciones * (porc_prima_vacacional / 100.0)) / 365.0 * self.dias_base
            #_logger.info("prima_vacacional: %s" % prima_vacacional)
            #_logger.info("aguinaldo: %s" % aguinaldo)
            
            
            data.update({
                'prestaciones_dias_vacaciones' : dias_vacaciones,
                'prestaciones_prima_vacacional': porc_prima_vacacional,
                'prestaciones_dias_aguinaldo'  : dias_aguinaldo,
                'factor_integracion'           : contract.cfdi_sueldo_base and  ((contract.cfdi_sueldo_base * self.dias_base) + prima_vacacional + aguinaldo) / (contract.cfdi_sueldo_base * self.dias_base) or 0,
            })
            
            
            last_imss_sbc = imss_sbc_obj.search([('employee_id','=',contract.employee_id.id),
                                                ('state','=','confirm')], limit=1)
            
            if last_imss_sbc:
                data.update({'sbc_actual_ultima_modif' : last_imss_sbc.date,
                             'sbc_actual_ultima_modif2' : last_imss_sbc.date,
                             'sbc_actual_parte_variable' : last_imss_sbc.sbc_nuevo_parte_variable,
                             'sbc_actual_sbc'   : last_imss_sbc.sbc_nuevo_sbc or (contract.sdi_ids and contract.sdi_ids[0].amount or contract.date_start),
                             })
            else:
                data.update({'sbc_actual_ultima_modif' : contract.sdi_ids and contract.sdi_ids[0].date or contract.date_start,
                             'sbc_actual_ultima_modif2' : contract.sdi_ids and contract.sdi_ids[0].date or contract.date_start,
                             'sbc_actual_parte_variable' : 0,
                             'sbc_actual_sbc'   : contract.sdi_ids and contract.sdi_ids[0].amount or contract.cfdi_sueldo_base,
                             
                             })
            
            
            dias_base = self.dias_base if contract.fecha_ingreso <= self.date_from else ((self.date_to - contract.fecha_ingreso).days + 1)
            #_logger.info("dias_base: %s" % dias_base)
            data.update({'sbc_nuevo_parte_fija' : ((contract.cfdi_sueldo_base * self.dias_base) + prima_vacacional + aguinaldo) / self.dias_base,
                         'sbc_nuevo_fecha_aplicacion' : self.date,
                         'dias_base'        : dias_base})
            
            desde = fecha_alta if fecha_alta > self.date_from else self.date_from
            desde = fecha_alta if fecha_alta > self.date_from else self.date_from
            if fecha_alta > self.date_from:
                payslip_lines = payslip_line_obj.read_group([
                    ('slip_id.employee_id','=',contract.employee_id.id),
                    ('slip_id.state','=','done'),
                    ('slip_id.date_to','>=', fecha_alta),
                    ('slip_id.date_to','<=', self.date_to),
                    ('salary_rule_id','in',self.salary_rule_ids.ids),
                    ('imss_gravado','>',0)],
                    ['salary_rule_id', 'imss_gravado'], ['salary_rule_id']
                )
            else:
                payslip_lines = payslip_line_obj.read_group([
                    ('slip_id.employee_id','=',contract.employee_id.id),
                    ('slip_id.state','=','done'),
                    ('slip_id.date_from','>=', self.date_from),
                    ('slip_id.date_to','<=', self.date_to),
                    ('salary_rule_id','in',self.salary_rule_ids.ids),
                    ('imss_gravado','>',0)],
                    ['salary_rule_id', 'imss_gravado'], ['salary_rule_id']
                )
            
            #_logger.info("payslip_lines: %s" % payslip_lines)

            _incapacidades = incapacidades.get(contract.employee_id.id, 0.0)
            _faltas = faltas.get(contract.employee_id.id, 0.0)
            
            #_logger.info("_incapacidades: %s" % _incapacidades)
            #_logger.info("_faltas: %s" % _faltas)
            data.update({'dias_incapacidad' : _incapacidades or 0,
                         'dias_ausencia'    : _faltas or 0})
            
            dias_base = dias_base - (_incapacidades or 0) - (_faltas or 0)
            monto_vales_despensa = 0.0
            monto_exento_vales_despensa = dias_base * 0.4 * self.uma_id.monto
            sbc_nuevo_parte_variable = 0.0
            for x in payslip_lines:
                if param_vales_despensa and x['salary_rule_id'][0]==vale_despensa_id:
                    monto_vales_despensa += x['imss_gravado']
                else:
                    sbc_nuevo_parte_variable += x['imss_gravado']
            if param_vales_despensa and monto_vales_despensa and monto_exento_vales_despensa < monto_vales_despensa:
                sbc_nuevo_parte_variable += (monto_vales_despensa - monto_exento_vales_despensa)
            nuevo_sbc = min(self.uma_id.monto * 25.0, data['sbc_nuevo_parte_fija'] + (sbc_nuevo_parte_variable / float(dias_base or self.dias_base)))
            data.update({'total_percepciones_variables' : sbc_nuevo_parte_variable,
                         'sbc_nuevo_parte_variable' : sbc_nuevo_parte_variable / float(dias_base or self.dias_base),
                         'sbc_nuevo_sbc' :  nuevo_sbc
                        })
            lines.append((0,0,data))
        
        self.line_ids = lines
        self.create_excel_file()
        return True
    
    def create_imss_record(self):
        imss_obj = self.env['hr.employee.imss']
        
        contract_ids = [l.contract_id.id for l in self.line_ids.filtered(lambda w: w.aplicar_modificacion_sbc)]
        data ={'date'       : self.date,
               'date_from'  : self.date,
               'date_to'    : self.date,
               'type'       : '07',
               'contract_ids' : contract_ids,
               'notes'      : _('Registro creado desde Actualización Bimestral de SBC %s' % self.name)
              }
        _logger.info("data: %s" % data)
        imss_rec = imss_obj.new(data)
        imss_rec._onchange_contract_ids()
        data_modif = imss_rec._convert_to_write(imss_rec._cache)
        _logger.info("data_modif: %s" % data_modif)
        imss_id = imss_obj.create(data_modif)
        imss_id.action_confirm()
        
    def action_confirm(self):
        hr_contract_sdi_obj = self.env['hr.contract.sdi']
        contract_obj = self.env['hr.contract']
        contracts = [] 
        for l in self.line_ids.filtered(lambda w: w.aplicar_modificacion_sbc):
            if l.contract_id.id in contracts:
                continue
            contracts.append(l.contract_id.id)
            if not l.sbc_nuevo_sbc:
                raise ValidationError(_("No puede aplicar nuevo SBC en ceros para %s, por favor revise\n\n(Puede ordenar por la columna SBC Nuevo)") % l.contract_id.name)

            #_logger.info("=== %s - %s ===" % (l.contract_id.id, l.contract_id.name))
            #for contract in contract_obj.search([('employee_id','=', l.employee_id.id), ('state','!=','cancel')]):
            res = hr_contract_sdi_obj.create({
                        'contract_id' : l.contract_id.id,
                        'date'        : self.date,
                        'amount'      : l.sbc_nuevo_sbc,
                        'notes'       : _('Modificación Bimestral de Salario'),
                        'imss_sbc_line_id' : l.id})
                    
        self.create_file()
        self.write({'state':'confirm'})
        self.create_excel_file()
        self.create_imss_record()
        return True
        
    def action_cancel(self):
        res = self.env['hr.contract.sdi'].search([('imss_sbc_line_id','in',self.line_ids.ids)])
        res.unlink()
        self.write({'state':'cancel'})
        return True

    
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
            
    def create_file(self):
        idse = base64.encodestring(self.write_file('\r\n'.join([l.line_idse for l in self.line_ids.filtered(lambda w: w.aplicar_modificacion_sbc)])))
        idse_filename = self.date.isoformat() + '_MODIFICACION_BIM_SDI_IDSE.txt'
                         
        self.write({'idse' : idse,
                    'idse_filename' : idse_filename,
        })
        return True
    
    
    def action_view_details(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_payslip_analysis')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_search')
        pivot_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_pivot')
        graph_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_graph')

        result = {
            'name': _('Análisis IMSS Gravado - Referencia: %s') % self.name,
            'help': action.help,
            'type': action.type,
            'views': [[search_view_id, 'search'], [pivot_view_id, 'pivot'],  [graph_view_id, 'graph']],
            'target': 'fullscreen', # action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        result['context'] =  "{'pivot_measures': ['imss_gravado'], 'pivot_row_groupby': ['employee_id','salary_rule_id'],'pivot_column_groupby': ['date_from:day'],}"
        
        result['domain'] = "[('imss_gravado','!=',0), ('state','=','done'),('date_from','>=','%s'),('date_to','<=','%s'), ('employee_id','in',(%s))]" % \
                            (self.date_from.isoformat(),
                             self.date_to.isoformat(),
                             ','.join([str(x.employee_id.id) for x in self.line_ids])
                            )
        return result
    
    
    def action_view_lines(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll_imss.action_hr_employee_imss_sbc_line')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll_imss.hr_employee_imss_sbc_line_search')
        tree_view_id = imd.xmlid_to_res_id('l10n_mx_payroll_imss.hr_employee_imss_sbc_line_tree1')
        form_view_id = imd.xmlid_to_res_id('l10n_mx_payroll_imss.hr_employee_imss_sbc_line_form1')

        result = {
            'name': _('Líneas de Actualización de SBC %s') % self.name,
            'help': action.help,
            'type': action.type,
            #'views': [[search_view_id, 'search'], [form_view_id, 'form'],  [tree_view_id, 'tree']],
            'views': [[tree_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        result['domain'] = "[('imss_sbc_id','=',%s)]" % (self.id)
        return result
                
class HREmployeeIMSSSSBCLine(models.Model):
    _name="hr.employee.imss.sbc.line"
    _description ="Lineas de Actualizacion bimestral del SBC para IMSS"
    _order = 'date desc, employee_id'
                         
    
    def get_idse_line(self):
        type='07' # modificacion
        return '%s%s%s%s%s%s      %s%s%s%s%s%s%s           %s9' % \
                (self.company_id.registro_patronal,
                 self.employee_id.nss,
                 self.employee_id.apellido_paterno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                 self.employee_id.apellido_materno.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27] if self.employee_id.apellido_materno else (' '*27),
                 self.employee_id.nombre.replace('ñ','n').replace('Ñ','N').ljust(27, ' ')[:27],
                 '{:07.2f}'.format(self.contract_id.cfdi_salario_diario_integrado2 or self.contract_id.cfdi_salario_diario_integrado).replace('.',''),
                 self.contract_id.tipo_trabajador,
                 self.contract_id.tipo_salario,
                 self.contract_id.jornada_reducida,
                 self.date.strftime('%d%m%Y'),
                 ('{:03}'.format(self.employee_id.unidad_medicina_familiar) + '  ') if False else (' '*5),
                 '07',
                 '{:05}'.format(self.employee_id.clave_subdelegacion),
                 self.employee_id.curp or self.employee_id.address_home_id.curp
                )
    
    @api.depends('employee_id', 'contract_id')
    def _get_line(self):
        for l in self:
            # Validaciones IDSE
            if not l.imss_sbc_id.company_id.registro_patronal or len(l.imss_sbc_id.company_id.registro_patronal) != 11:
                raise ValidationError(_('Error !\nEl Registro patronal de la Empresa está mal definido, por favor revise'))
            if not l.employee_id.nss or len(l.employee_id.nss) != 11:
                raise ValidationError(_('Error !\nEl Número de Seguro Social del Trabajador %s no tiene 11 caracteres') % l.employee_id.name)
            if not l.contract_id.cfdi_sueldo_base or l.contract_id.cfdi_sueldo_base < 0:
                raise ValidationError(_('Error !\nEl SDI del Trabajador %s no puede ser igual o menor a cero') % l.employee_id.name)
            if not l.contract_id.tipo_trabajador:
                raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Trabajador para %s') % l.employee_id.name)
            if not l.contract_id.tipo_salario:
                raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Salario para %s') % l.employee_id.name)
            if not l.contract_id.jornada_reducida:
                raise ValidationError(_('Error !\nNo está definido el valor del Tipo de Jornada para %s') % l.employee_id.name)
            if not (l.employee_id.curp):
                raise ValidationError(_('Error !\nNo está definido la CURP para %s') % l.employee_id.name)
            if len(l.employee_id.curp) !=18:
                raise ValidationError(_('Error !\nLa CURP para %s no contiene 18 caracteres') % l.employee_id.name)
            
            l.line_idse = l.get_idse_line()

    
    
    imss_sbc_id = fields.Many2one('hr.employee.imss.sbc', string="Línea Actualización SBC",
                                 required=True, index=True)

    state = fields.Selection(related="imss_sbc_id.state", store=True, index=True)
    
    date = fields.Date(related="imss_sbc_id.date", store=True, index=True)
    
    contract_id = fields.Many2one('hr.contract', string="Contrato",
                                 required=True, index=True)
    
    employee_id =  fields.Many2one('hr.employee', string="Empleado",
                                   related="contract_id.employee_id",
                                   store=True, index=True)
    
    employee_num_empleado = fields.Char(related="employee_id.num_empleado", readonly=True,
                                       string="Num. Empleado")
    
    fecha_alta = fields.Date(string="Fecha Alta o Reingreso")
    
    antig_laboral = fields.Float(string="Antig. Laboral",
                                digits=(6,2))
    
    incapacitado_en_fecha_aplicacion = fields.Boolean(string="Incapacitado en Fecha de Aplicación")
    
    
    company_id = fields.Many2one('res.company', string='Compañía', 
                                 related="imss_sbc_id.company_id", store=True,
                                 readonly=True)
    
    registro_patronal = fields.Char(related="company_id.registro_patronal", readonly=True)
    
    employee_nss = fields.Char(related="employee_id.nss", readonly=True)
    
    contract_sindicalizado = fields.Selection(related="contract_id.sindicalizado", readonly=True)
    
    contract_tipo_salario = fields.Selection(related="contract_id.tipo_salario", readonly=True,
                                            string="Tipo Salario")
    
    prestaciones_dias_vacaciones = fields.Integer(string="Prestaciones - Días Vacaciones")
    prestaciones_prima_vacacional = fields.Float(string="Prestaciones - % Prima Vac.",
                                                digits=(7,2))
    prestaciones_dias_aguinaldo = fields.Integer(string="Prestaciones - Días Aguinaldo")
    
    factor_integracion = fields.Float(string="Factor Integración", digits=(12,4))
    
    line_idse = fields.Text(string="Línea TXT IDSE", compute="_get_line")
    
    contract_salario_diario = fields.Float(
        related="contract_id.cfdi_sueldo_base", readonly=True,
        string="Salario Diario")
    
    sbc_actual_parte_fija = fields.Float(
        related="contract_id.cfdi_sueldo_base", readonly=True,
        string="SBC Actual - Parte Fija")
    
    sbc_actual_ultima_modif = fields.Date(string="SBC Actual - Ultima Modif.")
    
    sbc_actual_parte_variable = fields.Float(string="SBC Actual - Parte Variable",
                                                     digits=(18,4))
    
    
    sbc_actual_ultima_modif2 = fields.Date(string="SBC Actual - Ultima Modif.2")
    
    sbc_actual_sbc = fields.Float(string="SBC Actual", digits=(18,4))
    
    
    sbc_nuevo_parte_fija = fields.Float(string="SBC Nuevo - Parte Fija", digits=(18,4))

    
    sbc_nuevo_parte_variable = fields.Float(string="SBC Nuevo - Parte Variable",
                                                     digits=(18,4))
    
    sbc_nuevo_fecha_aplicacion = fields.Date(string="SBC Nuevo - Aplicación")
    
    sbc_nuevo_sbc = fields.Float(string="SBC Nuevo", digits=(18,4))
    
    aplicar_modificacion_sbc = fields.Boolean(string="Aplicar Modificación",
                                             default=True)
    
    total_percepciones_variables = fields.Float(string="Total Perc. Variable",
                                                     digits=(18,4))
    
    dias_incapacidad = fields.Integer(string="Días Incapacidad", default=0)
    dias_ausencia = fields.Integer(string="Días Ausencia", default=0)
    
    dias_base = fields.Integer(string="Días Base", readonly=True)
        
    dias_bimestre = fields.Integer(string="Días Bimestre",
                              related="imss_sbc_id.dias_base", readonly=True)
    
    company_id          = fields.Many2one('res.company', related="imss_sbc_id.company_id")
    notes = fields.Text(string="Observaciones")
    
    
    @api.depends('dias_base','dias_incapacidad', 'dias_ausencia')
    def _get_dias_neto(self):
        for rec in self:
            rec.dias_neto = rec.dias_base - rec.dias_incapacidad - rec.dias_ausencia
    
    dias_neto = fields.Integer(string="Días Neto", compute="_get_dias_neto", store=True)
    
    def action_view_details(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_payslip_analysis')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_search')
        pivot_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_pivot')
        graph_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_graph')

        result = {
            'name': _('IMSS Gravado - Empleado: %s') % self.employee_id.name,
            'help': action.help,
            'type': action.type,
            'views': [[search_view_id, 'search'], [pivot_view_id, 'pivot'],  [graph_view_id, 'graph']],
            'target': 'fullscreen', # action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        result['context'] =  "{'pivot_measures': ['imss_gravado'], 'pivot_row_groupby': ['salary_rule_id'],'pivot_column_groupby': ['date_from:day'],}"
        desde = self.fecha_alta if self.fecha_alta > self.imss_sbc_id.date_from else self.imss_sbc_id.date_from
        result['domain'] = "[('imss_gravado','!=',0), ('employee_id','=',%s),('state','=','done'),('date_from','>=','%s'),('date_to','<=','%s')]" % \
                            (self.employee_id.id, 
                             desde.isoformat(),
                             self.imss_sbc_id.date_to.isoformat()
                            )

        return result
    
