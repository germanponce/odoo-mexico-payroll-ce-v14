# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from datetime import datetime, timedelta, date, time
from odoo.osv import expression
import math
import logging
_logger = logging.getLogger(__name__)


class HRLeaveGroup(models.Model):
    _name = 'hr.leave.group'
    _description = "Agrupacion para imprimir en Recibo de Nomina"
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Grupo", required=True)
    description = fields.Text(string="Descripción")
    leave_type_ids = fields.One2many('hr.leave.type', 'receipt_group_id',
                                    string="Tipos de Ausencias")
    

    
class HRLeaveType(models.Model):
    _inherit = 'hr.leave.type'
    
    hr_salary_rule_id = fields.Many2one('hr.salary.rule', string="Regla Salarial",
                                       help="Si indica una Regla salarial entonces al momento de crear una Ausencia "
                                            "de este tipo también se creará un Extra de Nómina por cada día del Rango "
                                            "de Ausencia")
    es_incapacidad = fields.Boolean(string="Es Incapacidad", index=True, default=False)
    tipoincapacidad_id  = fields.Many2one('sat.nomina.tipoincapacidad', string="·Tipo Incapacidad")
    receipt_group_id = fields.Many2one('hr.leave.group', string="Agrupación",
                                       help="Agrupación a usarse para Recibo de Nomina tipo Nomipaq")
    
class HRLeaves(models.Model):
    _inherit = 'hr.leave'

    dias        = fields.Integer(string="Duración del Evento", default=0)
    
    contract_id = fields.Many2one('hr.contract', string="Contrato", readonly=True,
                                  states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    date_start  = fields.Date(string="Inicio Periodo", index=True)
    date_end    = fields.Date(string="Final Periodo", index=True)
    vacaciones  = fields.Boolean(string="Son Vacaciones", index=True, 
                                 default=False, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    antiguedad  = fields.Integer(string="Antigüedad", required=True, default=0.0, 
                                 copy=False, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    hr_extra_ids = fields.One2many('hr.payslip.extra', 'leave_id', string="Extras de Nómina", 
                                  readonly=True, 
                                  states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    tipoincapacidad_id  = fields.Many2one('sat.nomina.tipoincapacidad', string="·Tipo Incapacidad", 
                                          store=True,
                                          related="holiday_status_id.tipoincapacidad_id", readonly=True)    
    es_incapacidad = fields.Boolean(string="Es Incapacidad", related="holiday_status_id.es_incapacidad",
                                    store=True, readonly=True)    
    #es_continuacion_incapacidad = fields.Boolean(string="Es Continuación de Incapacidad", index=True, 
    #                                             help="Active cuando la ausencia que está registrando es la continuación de una Incapacidad previa. Esto para que siga aplicando el Subsidio por Incapacidad correspondiente.",
    #                                             default=False)
    company_id          = fields.Many2one('res.company', 'Compañía', 
                                          default=lambda self: self.env.company)
    
    num_permiso_horas = fields.Integer(string="# Horas", default=0)
    es_permiso_horas = fields.Boolean(string="Permiso por Horas", default=False)
                                       
    
    @api.onchange('dias','request_date_from')
    def _onchange_dias_request_date_from(self):
        if self.dias:
            self.request_date_to = self.request_date_from + timedelta(days=self.dias-1)                                   
                                       
                                       
    # Se sobreescribe el metodo por un bug en el calculo de dias
    def _get_number_of_days2(self, date_from, date_to, employee_id):
        """ Returns a float equals to the timedelta between two dates given as string."""
        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            _logger.info("employee.get_work_days_data(date_from, date_to): %s" % employee.get_work_days_data(date_from, date_to))
            if self.request_unit_half:
                x = 0.5
            else:
                x = math.ceil(employee.get_work_days_data(date_from, date_to)['days'])
            return x
            #return employee.get_work_days_data(date_from, date_to)['days']

        today_hours = self.env.user.company_id.resource_calendar_id.get_work_hours_count(
            datetime.combine(date_from.date(), time.min),
            datetime.combine(date_from.date(), time.max),
            False)

        return self.env.user.company_id.resource_calendar_id.get_work_hours_count(date_from, date_to) / (today_hours or HOURS_PER_DAY)

    
    
    # Se sobreescribe el metodo por un bug en el calculo de horas
    
    @api.depends('number_of_days')
    def _compute_number_of_hours_display2(self):
        for holiday in self:
            calendar = holiday.employee_id.resource_calendar_id or self.env.user.company_id.resource_calendar_id
            if holiday.date_from and holiday.date_to:
                _logger.info("holiday.date_from => holiday.date_to: %s - %s" % (holiday.date_from, holiday.date_to))
                _logger.info("holiday.request_date_from => holiday.request_date_to: %s - %s" % (holiday.request_date_from, holiday.request_date_to))
                if holiday.request_unit_hours:
                    number_of_hours = (holiday.date_to - holiday.date_from).seconds/3600.0 or calendar.get_work_hours_count(holiday.date_from, holiday.date_to)
                elif holiday.request_unit_half:
                    number_of_hours = HOURS_PER_DAY / 2.0
                else:
                    number_of_hours = calendar.get_work_hours_count(holiday.date_from, holiday.date_to)
                holiday.number_of_hours_display = number_of_hours or (holiday.number_of_days * HOURS_PER_DAY)
            else:
                holiday.number_of_hours_display = 0
    
    
    def action_approve(self):
        res = super(HRLeaves, self).action_approve()
        extra_obj = self.env['hr.payslip.extra']
        for holiday in self.filtered(lambda x: x.holiday_type == 'employee'):
            if holiday.holiday_status_id.hr_salary_rule_id:
                date_from = holiday.date_from
                date_to = holiday.date_to
                data = {'employee_id'       : holiday.employee_id.id,
                        'hr_salary_rule_id' : holiday.holiday_status_id.hr_salary_rule_id.id,
                        'leave_id'        : holiday.id,
                       }
                if holiday.request_unit_hours or holiday.request_unit_half:
                    if not (0.5 <= holiday.number_of_hours_display <= HOURS_PER_DAY):
                        raise ValidationError(_('Advertencia!\n\nLa Ausencia es invalida porque el periodo es menor a media hora y mayor al máximo de %s horas por dia') % HOURS_PER_DAY)
                    
                    data['date'] = date_from.strftime('%Y-%m-%d')
                    extra = extra_obj.new(data)
                    extra.onchange_employee()
                    extra_data = extra._convert_to_write(extra._cache)
                    extra_data['amount'] = extra_data['amount'] / HOURS_PER_DAY * holiday.number_of_hours_display
                    rec = extra_obj.create(extra_data)
                    rec.action_confirm()
                    rec.action_approve()
                else:
                    _logger.info("SI ENTRA !!!")
                    xdias = 0                    
                    for dias in range((date_to - date_from).days+1):
                        fecha = date_from + timedelta(days=dias)
                        #if fecha.weekday() == 6 and not holiday.es_incapacidad: # Domingo, no se toma en cuenta, deberia ?
                        #    xdias += 1
                        #    continue
                        data['date'] = fecha.strftime('%Y-%m-%d')
                        extra = extra_obj.new(data)
                        extra.onchange_employee()
                        extra_data = extra._convert_to_write(extra._cache)
                        if not extra_data.get('contract_id', False):
                            raise ValidationError(_("Advertencia!\nEl Empleado no tiene Contrato válido para la fecha de la Ausencia..."))
                        rec = extra_obj.create(extra_data)
                        rec.action_confirm()
                        rec.action_approve()
            else:
                for extra in holiday.hr_extra_ids:
                    if extra.state=='draft':
                        extra.action_confirm()
                    if extra.state=='confirmed':
                        extra.action_approve()
        return res

    
    def action_refuse(self):
        res = super(HRLeaves, self).action_refuse()        
        for rec in self.filtered(lambda x: x.state=='refuse' and not x.payslip_status):
            rec.hr_extra_ids.action_reject()
            rec.hr_extra_ids.write({'leave_id' : False})
        return res
        

    
    
        
    
