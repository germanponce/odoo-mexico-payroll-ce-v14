# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import float_compare, float_is_zero, float_round, date_utils
from odoo.osv import expression
from datetime import datetime, timedelta, date
import pytz
from pytz import timezone
import xml
import codecs
from lxml import etree
from lxml.objectify import fromstring
import logging
_logger = logging.getLogger(__name__)

meses = ['dummy','Enero','Febrero','Marzo','Abril','Mayo', 'Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
dias_semana = ['Lun','Mar','Mie','Jue','Vie','Sab','Dom']


class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'
    _order = "sequence, contract_id"
    
    #hr.settlement
    state = fields.Selection(store=True, related='slip_id.state',
                             readonly=True)
    
    tipo_gravable      = fields.Selection(related="salary_rule_id.tipo_gravable")
    
    appears_on_payslip = fields.Boolean(string="Appears on Payslip", related='salary_rule_id.appears_on_payslip',
                                        readonly=True, store=True)
    
    no_suma = fields.Boolean(string="No Suma", related='salary_rule_id.no_suma',
                                        readonly=True, store=True)
    
    es_subsidio_causado = fields.Boolean(string="Es Subsidio Causado", related='salary_rule_id.no_suma',
                                        readonly=True, store=True)
    sequence = fields.Integer(string="Seq", related="salary_rule_id.sequence", store=True, readonly=True)
    
    settlement_id = fields.Many2one('hr.settlement', string="Finiquito / Liquidación",
                                    related='slip_id.settlement_id', store=True,
                                    index=True)
    
    company_id = fields.Many2one('res.company', related="slip_id.company_id", store=True, index=True)
    
    
    @api.depends('salary_rule_id')
    def _get_gravado_exento(self):
        for rec in self:
            rec.monto_exento = 0.0
            rec.monto_gravado = 0.0
            _logger.info("Regla: %s - %s - %s" % (rec.salary_rule_id.name, rec.salary_rule_id.nomina_aplicacion, rec.total))
            if rec.salary_rule_id.nomina_aplicacion=='percepcion':
                if rec.salary_rule_id.tipo_gravable=='gravable':
                    _logger.info("11111111111")
                    rec.monto_gravado = rec.total
                else:
                    _logger.info("22222222222")
                    rec.monto_exento = rec.total
            
                
    
    
    monto_gravado = fields.Float("Gravado", digits=(16,2), required=False, store=False,
                                 compute="_get_gravado_exento")
    
    monto_exento = fields.Float("Exento", digits=(16,2), required=False, store=False,
                                compute="_get_gravado_exento")
    
    
    
    @api.onchange('salary_rule_id')
    def _onchange_salary_rule_id(self):
        if self.salary_rule_id:
            self.code = self.salary_rule_id.code
            self.name = self.salary_rule_id.name
            self.category_id = self.salary_rule_id.category_id.id


    
class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'
    
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Description', required=False)
    payslip_extra_id = fields.Many2one('hr.payslip.extra', string="Extra de Nómina")
    
    payslip_extra_name    = fields.Char(string="Referencia", related="payslip_extra_id.name", readonly=True)
    
    payslip_extra_date    = fields.Date(string='Fecha', related="payslip_extra_id.date", readonly=True)
    
    
    payslip_extra_hr_salary_rule_id   = fields.Many2one('hr.salary.rule', string='Concepto',
                                                        related="payslip_extra_id.hr_salary_rule_id", readonly=True)
    
    code = fields.Char(related='payslip_extra_hr_salary_rule_id.code', readonly=True, store=True, required=False)
    name = fields.Char(related='payslip_extra_hr_salary_rule_id.name', readonly=True, store=True, required=False)
    
    payslip_extra_sat_nomina_tipohoraextra_id  = fields.Many2one('sat.nomina.tipohoraextra', string="Tipo Hora Extra",
                                                                 related="payslip_extra_id.sat_nomina_tipohoraextra_id", readonly=True)
                                                                 
    payslip_extra_qty                 = fields.Float(string='Cantidad', digits=(16,4),
                                                     related="payslip_extra_id.qty", readonly=True)
    
    payslip_extra_amount = fields.Float(string='Base', digits=(18,2),
                                        related="payslip_extra_id.amount", readonly=True)
    
    def reschedule_extra(self):
        if not(self.payslip_extra_id and self.env.user.company_id.reprogramar_extras_al_eliminar_de_nomina):
            raise ValidationError(_("No puede Re-programar un renglón de Otras Entradas si no está ligado a un Extra de Nómina"))
        dias = 7 if self.payslip_id.contract_id.sat_periodicidadpago_id.code=='02' else (15 if self.payslip_id.contract_id.sat_periodicidadpago_id.code=='04' else 0)
        _logger.info("self.payslip_extra_id: %s - %s - %s" % (self.payslip_extra_id.id, self.payslip_extra_id.name, self.payslip_extra_id.date))
        new_date = (self.payslip_extra_id.date + timedelta(days=dias))
        wiz_id = self.env['hr.payslip.input.reschedule'].create(
            {'input_line_id' : self.id,
             'extra_id' : self.payslip_extra_id.id,
             'new_date' : new_date
            })
        return {'type'      : 'ir.actions.act_window',
                'res_id'    : wiz_id.id,
                'view_mode' : 'form',
                'view_type' : 'form',
                'res_model' : 'hr.payslip.input.reschedule',
                'target'    : 'new',
                'name'      : 'Re-Programar Extra de Nómina'}
    
    
    def unlink(self):
        if any(w.payslip_extra_id for w in self) and self.env.user.company_id.reprogramar_extras_al_eliminar_de_nomina:
            raise ValidationError(_("No puede eliminar un renglón de Otras Entradas cuando está ligado a un Extra de Nómina, Descarte los cambios."))
        elif any(w.payslip_extra_id for w in self):
            for rec in self.filtered(lambda w: w.payslip_extra_id):
                rec.payslip_extra_id.write({'state':'approved'})
                if rec.payslip_extra_id.extra_discount_id and rec.payslip_extra_id.extra_discount_id.state=='done':
                    rec.payslip_extra_id.extra_discount_id.write({'state':'progress'})
        return super(HrPayslipInput, self).unlink()
    
    
    

class HRPayslip(models.Model):
    _inherit = 'hr.payslip'
    _rec_name = 'number'
    
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.number or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('number', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    

    
    @api.model
    def create(self, values):
        res = super(HRPayslip, self).create(values)
        for line in res.input_line_ids.filtered(lambda l: l.payslip_extra_id):
            line.payslip_extra_id.write({'state':'done'})
            if line.payslip_extra_id.extra_discount_id and line.payslip_extra_id.extra_discount_id.saldo<=0.01:
                line.payslip_extra_id.extra_discount_id.write({'state':'done'})
        return res
    
    
    
    def write(self, values):
        if 'date_from' in values or 'date_to' in values:
            raise ValidationError(_('Advertencia!\nNo puede cambiar el periodo una vez que ha guardado la Nómina, primero Cancele y reintente la operación'))
        if 'state' in values and values['state']=='cancel':
            for rec in self:
                for line in rec.input_line_ids.filtered(lambda l: l.payslip_extra_id):
                    line.payslip_extra_id.write({'state':'approved'})
                    if line.payslip_extra_id.extra_discount_id and line.payslip_extra_id.extra_discount_id.state=='done':
                        line.payslip_extra_id.extra_discount_id.write({'state':'progress'})
                rec.input_line_ids.write({'payslip_extra_id': False})
        elif 'state' in values and values['state']=='done':
            for rec in self:
                for line in rec.input_line_ids.filtered(lambda l: l.payslip_extra_id and l.payslip_extra_id.extra_discount_id):
                    if line.payslip_extra_id.extra_discount_id.saldo <= 0.01:
                        line.payslip_extra_id.extra_discount_id.write({'state':'done'})
        res = super(HRPayslip, self).write(values)
        if not ('state' in values and values['state']=='cancel'):
            for rec in self:
                self._cr.execute("update hr_payslip_line set amount=%s, total=%s where slip_id=%s and code ilike 'net%%';" % (rec.neto_a_pagar, rec.neto_a_pagar, rec.id))
        return res
    
    
    @api.depends('date_from', 'date_to')
    def _get_data_from_date_range(self):
        tz_utc = pytz.timezone('UTC')

        for payslip in self:
            fecha1 = payslip.date_from
            fecha2 = payslip.date_to
            dias_periodo = (fecha2 - fecha1).days + 1
            dias_domingos = len([fecha1 + timedelta(days=x) for x in range((fecha2-fecha1).days + 1) if (fecha1 + timedelta(days=x)).weekday() == 6])
            dias_feriados = 0
            for single_date in [d for d in (fecha1 + timedelta(n) for n in range(dias_periodo)) if d <= fecha2]:
                tz = pytz.timezone(payslip.contract_id.resource_calendar_id.tz or 'Mexico/General')
                for leave in payslip.contract_id.resource_calendar_id.global_leave_ids:
                    date_from = tz_utc.localize(leave.date_from).astimezone(tz).replace(tzinfo=None)
                    date_to = tz_utc.localize(leave.date_to).astimezone(tz).replace(tzinfo=None)
                    if date_from.date() <= single_date <= date_to.date():
                        dias_feriados += 1
            
            payslip.update({'dias_periodo'      : dias_periodo,
                            'dias_domingos'     : dias_domingos,
                            'dias_feriados'     : dias_feriados,
                            'dias_trabajados'   : dias_periodo - dias_domingos - dias_feriados,
                           })
    
    @api.depends('date_to')
    def _get_fondo_ahorro(self):
        payslip_obj = self.env['hr.payslip']
        payslip_line_obj = self.env['hr.payslip.line']
        salary_rule_obj = self.env['hr.salary.rule']
        for payslip in self:
            year = str(payslip.date_to.year)
            date_from = date(payslip.date_to.year, 1, 1)
            payslips = payslip_obj.search([('employee_id','=',payslip.employee_id.id),
                                           ('date_from','>=', date_from),
                                           ('date_to','<=',payslip.date_to),
                                           ('state','=','done')],
                                          order='date_to asc'
                                         )
            regla_fa_empresa = salary_rule_obj.search([('otro_clasificador','=','fondo_ahorro_empresa')], limit=1)
            regla_fa_empleado = salary_rule_obj.search([('otro_clasificador','=','fondo_ahorro_empleado')], limit=1)
            lineas_empresa = payslip_line_obj.search([('slip_id','in', payslips.ids),
                                                      ('salary_rule_id','=',regla_fa_empresa.id)])
            monto_fa_empresa = sum(lineas_empresa.mapped('total')) or 0.0
            lineas_empleado = payslip_line_obj.search([('slip_id','in', payslips.ids),
                                                       ('salary_rule_id','=',regla_fa_empleado.id)])
            monto_fa_empleado = sum(lineas_empleado.mapped('total')) or 0.0
            payslip.update({'fondo_ahorro_empresa' : monto_fa_empresa,
                            'fondo_ahorro_empleado': monto_fa_empleado,
                           })



    @api.depends('line_ids.amount')
    def _get_payroll_resume(self):
        for payslip in self:
            incapacidades_monto, total_indemnizacion = 0.0, 0.0
            indemnizacion_ultimo_sueldo_ordinario = 0.0
            percepciones_gravadas, percepciones_exentas, percepciones = 0.0, 0.0, 0.0
            percepciones_regulares, percepciones_no_suma, deducciones = 0.0, 0.0, 0.0
            otrospagos_regulares, otrospagos_no_suma, otrospagos, otrospagos_xml = 0.0, 0.0, 0.0, 0.0
            incapacidad, neto, retenciones = 0.0, 0.0, 0.0
            subsidio_pagado = 0.0
            
            indemnizacion_antiguedad = payslip.settlement_id and round(payslip.settlement_id.antig_anios) or 0
            
            indemnizacion_ultimo_sueldo_ordinario = sum(payslip.line_ids.filtered(lambda x: x.salary_rule_id.code=='FQT_ULT_SDO_MES_ORD').mapped('total'))

            for line in payslip.line_ids.filtered(lambda x: x.salary_rule_id.appears_on_payslip):
                total_indemnizacion += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' \
                                                    and line.salary_rule_id.tipopercepcion_id.code in ('022','025') else 0.0
            
                incapacidades_monto += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' \
                                                    and line.salary_rule_id.tipopercepcion_id.code=='014' else 0.0
                percepciones_gravadas += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                       line.salary_rule_id.tipo_gravable == 'gravable' else 0.0
                percepciones_exentas += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                      line.salary_rule_id.tipo_gravable == 'exento' else 0.0
                    
                percepciones+= line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' else 0.0
                percepciones_regulares += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                        not line.salary_rule_id.no_suma else 0.0
                percepciones_no_suma += line.total if line.salary_rule_id.nomina_aplicacion == 'percepcion' and \
                                                         line.salary_rule_id.no_suma else 0.0
                deducciones += line.total if line.salary_rule_id.nomina_aplicacion == 'deduccion' else 0.0
                retenciones += line.total if line.salary_rule_id.nomina_aplicacion == 'deduccion' and \
                                             line.salary_rule_id.tipodeduccion_id.code =='002' else 0.0
                                
                otrospagos_regulares += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' and not line.salary_rule_id.no_suma else 0.0
                otrospagos_no_suma += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' and line.salary_rule_id.no_suma else 0.0
                otrospagos  += line.total if line.salary_rule_id.nomina_aplicacion == 'otrospagos' else 0.0
                if line.salary_rule_id.nomina_aplicacion == 'otrospagos':
                    if line.salary_rule_id.es_subsidio_causado and line.total:
                        otrospagos_xml  += 0.01 if not any(x.salary_rule_id.tipootropago_id.code in ('007','008') for x in payslip.otrospagos_ids) else 0.0
                    elif not line.salary_rule_id.es_subsidio_causado: # and line.salary_rule_id.tipootropago_id.code!='002':
                        otrospagos_xml  += line.total
                    if not line.salary_rule_id.es_subsidio_causado and line.salary_rule_id.tipootropago_id.code =='002':
                        subsidio_pagado += line.total
                
                incapacidad += line.total if line.salary_rule_id.nomina_aplicacion == 'incapacidad' else 0.0
            
            if subsidio_pagado and any(_q.salary_rule_id.tipootropago_id.code in ('007','008') and _q.total for _q in payslip.line_ids.filtered(lambda x: x.salary_rule_id.nomina_aplicacion == 'otrospagos' and x.salary_rule_id.appears_on_payslip)):
                otrospagos_xml -= subsidio_pagado
            elif subsidio_pagado:
                otrospagos_xml -= 0.01
                
            payslip.update({'sum_percepciones_gravadas' : percepciones_gravadas,
                            'sum_percepciones_exentas'  : percepciones_exentas,
                            'sum_percepciones_regulares': percepciones_regulares,
                            'sum_percepciones_no_suma' : percepciones_no_suma,
                            'sum_percepciones'  : percepciones - total_indemnizacion,
                            'sum_deducciones'   : deducciones,
                            'sum_otrospagos_regulares' : otrospagos_regulares,
                            'sum_otrospagos_no_suma'   : otrospagos_no_suma,
                            'sum_otrospagos'    : otrospagos,
                            'sum_otrospagos_xml' : otrospagos_xml,
                            'subsidio_pagado' : subsidio_pagado,
                            'sum_incapacidad'   : incapacidad,
                            'total_percepciones': percepciones + otrospagos_regulares,
                            'total_retenciones': retenciones,
                            'neto_a_pagar'  : percepciones_regulares - deducciones + otrospagos_regulares,
                            'total_incapacidades' : incapacidades_monto,
                            'total_indemnizacion' : total_indemnizacion,
                            'indemnizacion_antiguedad' : indemnizacion_antiguedad,
                            'indemnizacion_ultimo_sueldo_ordinario' : indemnizacion_ultimo_sueldo_ordinario,
                            })
                    
    @api.depends('payslip_datetime')
    def _get_date_payslip_tz(self):
        tz = self.env.user.partner_id.tz or 'America/Mexico_City'
        for rec in self:
            rec.date_payslip_tz = rec.payslip_datetime and rec.server_to_local_timestamp(
                rec.payslip_datetime, DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, tz) or False
        
    
    @api.depends('number')
    def _get_serie_folio(self):
        separadores = ['/','-','.',' ']
        for payslip in self:
            serie, folio = '',''
            if payslip.number:
                for separador in separadores:
                    if payslip.number.find(separador) >= 1 and len(payslip.number.split(separador)) == 2:
                        serie = payslip.number.split(separador)[0]
                        folio = payslip.number.split(separador)[1]
            payslip.sat_serie = serie
            payslip.sat_folio = folio
    
    

    @api.depends('line_ids.amount','input_line_ids')
    def _get_data_extra_hours(self):
        for rec in self:
            gravado, exento, monto, monto_doble, monto_triple = 0.0, 0.0, 0.0, 0.0, 0.0
            dias_doble, dias_triple, qty_doble, qty_triple = 0, 0, 0, 0
            code, name = '', ''
            for line in rec.line_ids.filtered(lambda x: x.salary_rule_id.tipopercepcion_id.code=='019'):
                name    = line.salary_rule_id.name
                code    = line.salary_rule_id.code
                gravado += line.amount if line.salary_rule_id.tipo_gravable == 'gravable' else 0
                exento  += line.amount if line.salary_rule_id.tipo_gravable == 'exento' else 0
            monto   += (gravado + exento)

            _dias_doble, _dias_triple = [], []
            for line in rec.input_line_ids.filtered(lambda x: x.code=='HORAS_EXTRAS' and x.payslip_extra_id):
                horas_turno = (line.payslip_extra_id.contract_id.sat_tipojornada_id.code=='01' and 8.0 or 0) or \
                                (line.payslip_extra_id.contract_id.sat_tipojornada_id.code=='02' and 7.0 or 0) or \
                                (line.payslip_extra_id.contract_id.sat_tipojornada_id.code=='03' and 7.5 or 0) if \
                                (line.payslip_extra_id.contract_id.sat_tipojornada_id and \
                                 line.payslip_extra_id.contract_id.sat_tipojornada_id.code in ('01', '02', '03')) else 8
                sueldo_x_hora = line.payslip_extra_id.amount / (horas_turno or 8)
                if line.payslip_extra_id.sat_nomina_tipohoraextra_id.code == '01': # Dobles
                    if line.payslip_extra_id.date not in _dias_doble:
                        _dias_doble.append(line.payslip_extra_id.date)
                    monto_doble += (line.payslip_extra_id.qty * sueldo_x_hora * 2)
                    qty_doble += line.payslip_extra_id.qty
                elif line.payslip_extra_id.sat_nomina_tipohoraextra_id.code == '02': # Triples
                    if line.payslip_extra_id.date not in _dias_triple:
                        _dias_triple.append(line.payslip_extra_id.date)
                    monto_triple += (line.payslip_extra_id.qty * sueldo_x_hora * 3)
                    qty_triple += line.payslip_extra_id.qty
            dias_doble = len(_dias_doble)
            dias_triple = len(_dias_triple)

            rec.update({'extra_hours_name' : name,
                         'extra_hours_code' : code,
                         'extra_hours_gravado' : gravado,
                         'extra_hours_exento'   : exento,
                         'extra_hours_monto'    : monto,
                         'extra_hours_monto_doble' : monto_doble,
                         'extra_hours_monto_triple' : monto_triple,
                         'extra_hours_dias_doble'   : dias_doble,
                         'extra_hours_dias_triple'  : dias_triple,
                         'extra_hours_qty_doble'    : monto_doble and (qty_doble or 1) or 0,
                         'extra_hours_qty_triple'   : monto_triple and (qty_triple or 1) or 0,
                    })
            
    @api.depends('input_line_ids','date_from','date_to')
    def _get_week_attendance(self):
        leave_obj = self.env['hr.leave']
        descanso = self.env['hr.leave.type'].search([('name','=','Descanso')], limit=1)
        if not descanso:
            raise ValidationError(_("No se encontró el Tipo de Ausencia para Descanso"))
        for rec in self:
            data = []
            dias = (rec.date_to - rec.date_from).days + 1
            fecha_base = rec.date_from
            for dia in range(dias):
                fecha = fecha_base + timedelta(days=dia)
                data.append({'dia_semana' : dias_semana[fecha.weekday()], 'valor' : ''})
                for _r in rec.input_line_ids.filtered(lambda w: w.payslip_extra_id.leave_id.holiday_status_id.receipt_group_id):
                    if _r.payslip_extra_id.leave_id.date_from.date() <= fecha <= _r.payslip_extra_id.leave_id.date_to.date():
                        data[dia]['valor'] = _r.payslip_extra_id.leave_id.holiday_status_id.receipt_group_id.code
                if not data[dia]['valor']:
                    res = leave_obj.search([('employee_id','=',rec.employee_id.id),
                                            ('state','=','validate'),
                                            ('holiday_type','=','employee'),
                                            ('date_from','>=',fecha),
                                            ('date_to','<=', fecha),
                                            ('holiday_status_id.receipt_group_id','!=',False)
                                           ])
                    
                    if res and res[0].holiday_status_id.id==descanso.id and rec.contract_id.department_id.dia_descanso_variable:
                        data[dia]['valor'] = res[0].holiday_status_id.receipt_group_id.code
                    elif res and res[0].holiday_status_id.id!=descanso.id:
                        data[dia]['valor'] = res[0].holiday_status_id.receipt_group_id.code
                    elif fecha.weekday()==6 and not rec.contract_id.department_id.dia_descanso_variable: # Domingo
                        data[dia]['valor'] = 'D'
                    else:
                        data[dia]['valor'] = 'X'
            
            rec.week_attendance = str(data)
    
    def convert_week_attendance(self):
        self.ensure_one()
        return eval(self.week_attendance)
    
    @api.depends('date_from','date_to')
    def _get_payslip_period_for_receipt(self):
        for rec in self:
            x, y = rec.date_from, rec.date_to
            if rec.date_from.year != rec.date_to.year:
                rec.period_string =  "Periodo del %s de %s de %s al %s de %s de %s" % (int(x.strftime('%d')), meses[int(x.strftime("%m"))], x.strftime("%Y"), int(y.strftime('%d')), meses[int(y.strftime("%m"))], y.strftime("%Y"))
            elif rec.date_from.month!=rec.date_to.month:
                rec.period_string = "Periodo del %s de %s al %s de %s de %s" % (int(x.strftime('%d')), meses[int(x.strftime("%m"))], int(y.strftime('%d')), meses[int(y.strftime("%m"))], x.strftime("%Y"))
            else:
                rec.period_string = "Periodo del %s al %s de %s de %s" % (x.strftime('%d'), y.strftime('%d'), meses[int(x.strftime("%m"))], x.strftime("%Y"))

    week_attendance = fields.Char(string="Asistencias de la Semana",
                                 compute="_get_week_attendance")
    period_string = fields.Char(string="Periodo en String", 
                                compute="_get_payslip_period_for_receipt")
    cfdi_timbrar = fields.Boolean(string="Timbrar?", default=True, index=True, readonly=True,
                                 states={'draft': [('readonly', False)], 'verify': [('readonly', False)]}, copy=False)
    """
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('verify', 'En Revisión'),
        ('done', 'Hecho'),
        ('cancel', 'Cancelada'),
    ], string='Estado', index=True, readonly=True, copy=False, default='draft',
        tracking=True,
        help="* Cuando una Nómina es creado por defecto el estado es \'Borrador\'."
        "\n* Si la Nómina está por Verificarse el estado es \'En Revisión\'"
        "\n* Si la Nómina se confirma entonces el estado es \'Hecho\'."
        "\n* Cuando se cancela la nómina queda en estado \'Cancelada\'.")
    """
    
    def action_view_analysis(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_hr_payslip_analysis')
        search_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_search')
        pivot_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_pivot')
        graph_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.view_hr_payslip_analysis_graph')

        result = {
            'name': _('Análisis Nómina - Referencia: %s') % self.number,
            'help': action.help,
            'type': action.type,
            'views': [[search_view_id, 'search'], [pivot_view_id, 'pivot'],  [graph_view_id, 'graph']],
            'target': action.target,#'fullscreen', # 
            'context': action.context,
            'res_model': action.res_model,
        }
        result['context'] =  "{'pivot_measures': ['amount'], 'pivot_row_groupby': ['nomina_aplicacion','salary_rule_id'],'pivot_column_groupby': ['number'], 'search_default_nomina_aplicacion_percepciones':1, 'search_default_nomina_aplicacion_deducciones':1, 'search_default_nomina_aplicacion_otrospagos':1, 'search_default_no_suma_0':1}"
        
        result['domain'] = "[('amount','!=',0), ('number','=','%s')]" % (self.number)
        _logger.info("result: %s" % result)
        return result
    
    def _compute_payslip_count(self):
        for payslip in self:
            payslip.payslip_count = len(payslip.line_ids)
    
    payslip_count = fields.Integer(compute='_compute_payslip_count', string="# Líneas")
    
    journal_id = fields.Many2one('account.journal', 'Diario Contable', readonly=True, required=False,
                                 related="struct_id.journal_id", store=True, index=True, tracking=True)
    contract_sindicalizado = fields.Selection(related='contract_id.sindicalizado', store=True, index=True)
    contract_department_id = fields.Many2one('hr.department', string="Departamento",
                                             related="contract_id.department_id", store=True, index=True)
    work_location = fields.Char(related="employee_id.work_location", string="Lugar de Trabajo",
                                store=True, index=True)
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches',
                                     readonly=False, copy=False, tracking=True)
    extra_hours_code    = fields.Char(string="Clave", compute=_get_data_extra_hours, store=False) 
    extra_hours_name    = fields.Char(string="Concepto", compute=_get_data_extra_hours, store=False)
    extra_hours_gravado = fields.Float(string="Gravado", digits=(18,2), readonly=True, 
                                       compute=_get_data_extra_hours, store=False)
    extra_hours_exento  = fields.Float(string="Exento", digits=(18,2), readonly=True, 
                                       compute=_get_data_extra_hours, store=False)
    extra_hours_monto   = fields.Float(string="Monto", readonly=True, 
                                       compute=_get_data_extra_hours, 
                                       store=False, digits=(18,2))
    extra_hours_monto_doble   = fields.Float(string="Monto Dobles", readonly=True, 
                                             compute=_get_data_extra_hours, 
                                             store=False, digits=(18,2))
    extra_hours_monto_triple   = fields.Float(string="Monto Triples", readonly=True, 
                                              compute=_get_data_extra_hours, 
                                              store=False, digits=(18,2))
    extra_hours_qty_doble  = fields.Integer(string="Cant. H.E. Dobles", default=0, 
                                            compute=_get_data_extra_hours, store=False)
    extra_hours_qty_triple = fields.Integer(string="Cant. H.E. Triples", default=0, 
                                            compute=_get_data_extra_hours, store=False)
    extra_hours_dias_doble  = fields.Integer(string="Dias H.E. Dobles", default=0, 
                                             compute=_get_data_extra_hours, store=False)
    extra_hours_dias_triple = fields.Integer(string="Dias H.E. Triples", default=0, 
                                             compute=_get_data_extra_hours, store=False)
    

    sat_serie           = fields.Char("Serie", compute="_get_serie_folio")
    sat_folio           = fields.Char("Folio", compute="_get_serie_folio")
    
    
    date_payroll    = fields.Date(string='Fecha de Pago', required=True, readonly=True, index=True,
                                  help="Fecha en que se realiza el pago de esta Nómina",
                                  tracking=True,
                                  default=fields.Date.context_today,
                                  states={'draft': [('readonly', False)]}, copy=False)
    
    payslip_datetime = fields.Datetime(string='Fecha CFDI', copy=False, readonly=True) 
    date_payslip_tz = fields.Datetime(string='Fecha CFDI con TZ', compute='_get_date_payslip_tz', copy=False)
    
    
    tiponomina_id   = fields.Many2one('sat.nomina.tiponomina','Tipo Nómina', required=True, 
                                      states={'draft': [('readonly', False)]}, readonly=True,
                                      default=lambda self: self.env['sat.nomina.tiponomina'].search([('code','=','O')], limit=1).id)
    salario_minimo  = fields.Many2one('sat.nomina.salario_minimo', string='Salario Mínimo', readonly=True,
                                      states={'draft': [('readonly', False)]})
    salario_minimo_fn  = fields.Many2one('sat.nomina.salario_minimo', string='Salario Mínimo FN', readonly=True,
                                      states={'draft': [('readonly', False)]})
    uma             = fields.Many2one('sat.nomina.uma_umi', string='UMA', readonly=True,
                                      tracking=True,
                                      states={'draft': [('readonly', False)]})
    
    umi             = fields.Many2one('sat.nomina.uma_umi', string='UMI', readonly=True,
                                      tracking=True,
                                      states={'draft': [('readonly', False)]})
    
    cfdi_sueldo_base= fields.Float('Sueldo Base', digits=(18,2), related="contract_id.cfdi_sueldo_base",
                                    store=True, readonly=True,
                                       help="Salario registrado ante el IMSS. Este se toma como\n"
                                            "base para los cálculos de Percepciones y Deducciones\n"
                                            "Puede ser Diario, por Hora, o según corresponda.")
    cfdi_factor_salario_diario_integrado = fields.Float(string='Factor SDI', digits=(18,6), 
                                                        store=True, readonly=True,
                                                        related="contract_id.cfdi_factor_salario_diario_integrado",
                                                        help="Factor para cálculo de Salario Diario Integrado")
    
    cfdi_salario_diario_integrado = fields.Float(string='Salario Diario Integrado', digits=(18,2), 
                                                 store=True, readonly=True,
                                                 related="contract_id.cfdi_salario_diario_integrado",
                                                 help="Salario Diario Integrado")
    
    dias_periodo = fields.Integer('Días del Periodo', compute='_get_data_from_date_range', store=True)
    dias_trabajados = fields.Integer('Días Trabajados', compute='_get_data_from_date_range', store=True)
    dias_domingos = fields.Integer('Días Domingos', compute='_get_data_from_date_range', store=True)
    dias_feriados = fields.Integer('Días Feriados', compute='_get_data_from_date_range', store=True)
            
    tabla_isr = fields.Many2many('sat.nomina.tabla_isr', compute='_get_tabla_isr', string="Tabla ISR",
                                 help="Es para poder usarla en el cálculo de las deducciones de las reglas")
    
    tabla_subsidio = fields.Many2many('sat.nomina.tabla_subsidio', compute='_get_tabla_subsidio', 
                                      string="Tabla Subsidio al Empleo",
                                      help="Es para poder usarla en el cálculo de las deducciones de las reglas")
    
    #factores_imss  = fields.Many2many('sat.nomina.factores_imss', compute='_get_tabla_factores_imss', 
    #                                  string="Factores IMSS",
    #                                  help="Tabla Factores para cálculo de conceptos del IMSS")
    
    percepciones_with_otrospagos_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Percepciones + Otros Pagos', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', 'in', ('percepcion','otrospagos')),
                                               ('total','!=',0)])
    
    percepciones_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Percepciones', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                               ('total','!=',0)])
    percepciones_regulares_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Percepciones Regulares', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                               ('total','!=',0),
                                               ('no_suma', '=', False)])
    percepciones_no_suma_ids = fields.One2many('hr.payslip.line', 'slip_id', 
                                               string='Percepciones en Especie', readonly=True,
                                                domain=[('appears_on_payslip','=',True),
                                                        ('salary_rule_id.nomina_aplicacion', '=', 'percepcion'),
                                                        ('total','!=',0),
                                                        ('no_suma', '=', True)])
    deducciones_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Deducciones', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'deduccion'),
                                               ('total','!=',0)])
    otrospagos_regulares_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Otros Pagos (Regulares)', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                               ('total','!=',0),
                                               ('no_suma', '=', False)])
    otrospagos_no_suma_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Otros Pagos (No suman)', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                               ('total','!=',0),
                                               ('no_suma', '=', True)])
    otrospagos_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Otros Pagos', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'otrospagos'),
                                               ('total','!=',0)])
    incapacidades_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Incapacidad', readonly=True,
                                       domain=[('appears_on_payslip','=',True),
                                               ('salary_rule_id.nomina_aplicacion', '=', 'incapacidad'),
                                               ('total','!=',0)])
    
    fondo_ahorro_empresa = fields.Float(string="Fondo Ahorro Empresa (Acum)",  compute_sudo=True,
                                        compute="_get_fondo_ahorro", digits=(18,2))
    fondo_ahorro_empleado = fields.Float(string="Fondo Ahorro Empleado (Acum)",  compute_sudo=True,
                                         compute="_get_fondo_ahorro", digits=(18,2))
    
    total_indemnizacion = fields.Float(string="Total Indemnización", 
                                       digits=(18,2), compute_sudo=True,
                                       compute="_get_payroll_resume", store=True)
    
    indemnizacion_antiguedad = fields.Integer(string="Indemnizacion Antiguedad",  compute_sudo=True,
                                              compute="_get_payroll_resume", store=True)
    
    indemnizacion_ultimo_sueldo_ordinario = fields.Float(string="Ultimo Sueldo Ordinario", 
                                                         digits=(18,2),  compute_sudo=True,
                                                         compute="_get_payroll_resume", store=True)
    
    
    total_incapacidades = fields.Float(string="Total Incapacidades", 
                                       digits=(18,2),  compute_sudo=True,
                                       compute="_get_payroll_resume", store=True)
    
    total_retenciones= fields.Float(string="Total Retenciones", digits=(18,2),  compute_sudo=True,
                                    compute="_get_payroll_resume", store=True)
    total_percepciones= fields.Float(string="Total Percepciones", digits=(18,2),  compute_sudo=True,
                                     compute="_get_payroll_resume", store=True)
    sum_percepciones_regulares = fields.Float(string="Subtotal Percepciones Regulares (+)",  compute_sudo=True,
                                              digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones_no_suma = fields.Float(string="Subtotal Percepciones en Especie (+)",  compute_sudo=True,
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones= fields.Float(string="Suma Percepciones (+)", digits=(18,2),  compute_sudo=True,
                                   compute="_get_payroll_resume", store=True)
    sum_percepciones_gravadas= fields.Float(string="Percepciones Gravadas",  compute_sudo=True,
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_percepciones_exentas = fields.Float(string="Percepciones Exentas",  compute_sudo=True,
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_deducciones = fields.Float(string="Total Deducciones (-)",  digits=(18,2),  compute_sudo=True,
                                   compute="_get_payroll_resume", store=True)
    sum_otrospagos_regulares = fields.Float(string="Subtotal Otros Pagos Regulares (+)",  compute_sudo=True,
                                            digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_otrospagos_no_suma = fields.Float(string="Subtotal Otros Pagos (No Suma) (+)",  compute_sudo=True,
                                          digits=(18,2), compute="_get_payroll_resume", store=True)
    sum_otrospagos  = fields.Float(string="Total Otros Pagos (+)", digits=(18,2),  compute_sudo=True,
                                   compute="_get_payroll_resume", store=True)
    sum_otrospagos_xml  = fields.Float(string="Total Otros XML", digits=(18,2),  compute_sudo=True,
                                       compute="_get_payroll_resume", store=True)
    subsidio_pagado  = fields.Float(string="Subsidio Pagado", digits=(18,2),  compute_sudo=True,
                                       compute="_get_payroll_resume", store=True)
    sum_incapacidad = fields.Float(string="Total Incapacidad (+)",  digits=(18,2),  compute_sudo=True,
                                   compute="_get_payroll_resume", store=True)
    neto_a_pagar    = fields.Monetary(string="Neto a Pagar",   compute_sudo=True,
                                   compute="_get_payroll_resume", store=True)
    
    settlement_id = fields.Many2one('hr.settlement', string="Finiquito / Liquidación", index=True,
                                   tracking=True)
    
    @api.constrains('employee_id', 'date_from', 'date_to', 'state')
    def _check_for_no_payslip_with_overlapping_range_dates(self):
        for rec in self.filtered(lambda x: x.state in ('draft','verify','done') and x.tiponomina_id.code=='O'):
            self._cr.execute("select id from hr_payslip "
                             "where id <> %s and employee_id=%s "
                             "and tiponomina_id=(select id from sat_nomina_tiponomina where code='O') "
                             "and state in ('draft','verify','done') "
                             "and (('%s' between date_from and date_to) or "
                             "('%s' between date_from and date_to) or "
                             "('%s' <= date_from and '%s' >= date_to) or "
                             "('%s' >= date_from and '%s' <= date_to));" % \
                             (rec.id, rec.employee_id.id, 
                              fields.Date.to_string(rec.date_from), fields.Date.to_string(rec.date_to), 
                              fields.Date.to_string(rec.date_from), 
                              fields.Date.to_string(rec.date_to), 
                              fields.Date.to_string(rec.date_from), fields.Date.to_string(rec.date_to)))
            xdata = self._cr.fetchall()
            datas = [_x[0] for _x in xdata]
            if len(datas):
                raise UserError(_('Rango de fechas incorrecto !\nNo puede tener nóminas del mismo empleado con fechas traslapadas\n\n- [%s] %s') % (rec.employee_id.id, rec.employee_id.name))
        return True
    
    
    # REVISAR si se estan generando correctamente las faltas en la nomina
    # ya que en v10 se tuvo que modificar este metodo (eliminar del final: _2)
    @api.model
    def get_worked_day_lines_2(self, contracts, date_from, date_to):
        res = []
        # fill only if the contract as a working schedule linked
        for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):
            day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
            day_to = datetime.combine(fields.Date.from_string(date_to), time.max)

            # compute leave days
            leaves = {}
            calendar = contract.resource_calendar_id
            tz = timezone(calendar.tz)
            day_leave_intervals = contract.employee_id.list_leaves(day_from, day_to, calendar=contract.resource_calendar_id)
            for day, hours, leave in day_leave_intervals:
                holiday = leave.holiday_id
                current_leave_struct = leaves.setdefault(holiday.holiday_status_id, {
                    'name': holiday.holiday_status_id.name or _('Global Leaves'),
                    'sequence': 5,
                    'code': holiday.holiday_status_id.name or 'GLOBAL',
                    'number_of_days': 0.0,
                    'number_of_hours': 0.0,
                    'contract_id': contract.id,
                })
                current_leave_struct['number_of_hours'] += hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )
                if work_hours:
                    current_leave_struct['number_of_days'] += hours / work_hours

            # compute worked days
            work_data = contract.employee_id.get_work_days_data(day_from, day_to, calendar=contract.resource_calendar_id)
            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': work_data['days'],
                'number_of_hours': work_data['hours'],
                'contract_id': contract.id,
            }

            res.append(attendances)
            res.extend(leaves.values())
        return res
    
    
    def compute_sheet(self):
        
        aplicar_calculo_inverso = self.env.user.company_id.aplicar_calculo_inverso
        rule_ids = self.env.user.company_id.reglas_para_calculo_inverso_ids.ids
        for payslip in self.filtered(lambda slip: slip.state not in ['cancel', 'done']):
            if not payslip.number:
                payslip.write({'number': self.env['ir.sequence'].next_by_code('salary.slip')})
                
            # delete old payslip lines
            payslip.line_ids.unlink()
            ## -- ## -- ##                
            if aplicar_calculo_inverso:
                monto = sum(payslip.input_line_ids.filtered(lambda w: w.payslip_extra_id.hr_salary_rule_id.id in rule_ids).mapped('amount'))
                if not monto:
                    lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                    payslip.write({'line_ids': lines})
                    continue
                
                # Obtenemos el Neto con Conceptos de calculo inverso (monto_con_conceptos)
                # 1. neto_con_conceptos
                lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                monto_con_conceptos = sum(l[2]['amount'] if l[2]['code'] in ('NET','ASM_NETO') else 0.0 for l in lines)
                if sum(l[2]['amount'] if l[2]['code'] =='OT_002' else 0.0 for l in lines):
                    monto_con_conceptos -= sum(l[2]['amount'] if l[2]['code'] =='Subsidio_Base' else 0.0 for l in lines)
                # Obtenemos el Neto sin Conceptos de calculo inverso (monto_sin_conceptos)
                # 2. Ponemos en cero las input lines para obtener el neto sin conceptos de calculo inverso
                input_line_ids = []
                for x in payslip.input_line_ids.filtered(lambda w: w.payslip_extra_id.hr_salary_rule_id.id in rule_ids):
                    input_line_ids.append({
                        'input_line' : x,
                        'amount' : x.amount,
                        'porcentaje' : x.amount / monto})
                    x.write({'amount' : 0})
                
                lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                monto_sin_conceptos = sum(l[2]['amount'] if l[2]['code'] in ('NET','ASM_NETO') else 0.0 for l in lines)
                if sum(l[2]['amount'] if l[2]['code'] =='OT_002' else 0.0 for l in lines):
                    monto_sin_conceptos -= sum(l[2]['amount'] if l[2]['code'] =='Subsidio_Base' else 0.0 for l in lines)
                monto_objetivo = round(monto_sin_conceptos + monto, 2)
                
                _logger.info("=== *** === *** ===")
                _logger.info("=== *** === *** ===")
                _logger.info("monto_sin_conceptos: %s" % monto_sin_conceptos)
                _logger.info("monto_con_conceptos: %s" % monto_con_conceptos)
                _logger.info("monto_objetivo: %s" % monto_objetivo)
                _logger.info("(monto_objetivo - monto_sin_conceptos) + (monto_objetivo - monto_con_conceptos): %s" % ((monto_objetivo - monto_sin_conceptos) + (monto_objetivo - monto_con_conceptos)))
                
                
                porcentaje = ((monto_objetivo - monto_sin_conceptos) + (monto_objetivo - monto_con_conceptos)) / monto_objetivo
                porcentaje = 0.1
                _logger.info("porcentaje: %s" % porcentaje)
                factor = 0.1
                monto_actual = round(monto_con_conceptos, 2)
                last_update = True
                cont = 0
                while not ((monto_objetivo + 0.01) > monto_actual > (monto_objetivo - 0.01)) and cont < 35:
                    cont += 1
                    _logger.info("= = = = = = = = = = =")
                    _logger.info("==== Intento: %s ====" % cont)
                    _logger.info("porcentaje anterior: %s" % porcentaje)
                    _logger.info("monto_objetivo: %s" % monto_objetivo)
                    _logger.info("monto_actual: %s" % monto_actual)
                    if (monto_objetivo - 0.01) > monto_actual:
                        if not last_update:
                            _logger.info("factor: %s" % factor)
                            last_update = True
                            factor = 0.05 if factor==0.1 else (0.01 if factor==0.05 else (0.005 if factor==0.01 else (0.001 if factor==0.005 else (0.0005 if factor==0.001 else (0.0001 if factor==0.0005 else (0.00005 if factor==0.0001 else (0.00001 if factor==0.00005 else (0.000005 if factor==0.00001 else (0.000001 if factor==0.000005 else (0.0000005 if factor==0.000001 else (0.0000001 if factor==0.0000005 else 0.00000001)))))))))))
                            _logger.info("factor: %s" % factor)
                        porcentaje += factor
                        _logger.info("aumenta porcentaje: %s" % porcentaje)
                    elif (monto_objetivo + 0.01) < monto_actual:
                        if last_update:
                            _logger.info("factor: %s" % factor)
                            last_update = False
                            factor = 0.05 if factor==0.1 else (0.01 if factor==0.05 else (0.005 if factor==0.01 else (0.001 if factor==0.005 else (0.0005 if factor==0.001 else (0.0001 if factor==0.0005 else (0.00005 if factor==0.0001 else (0.00001 if factor==0.00005 else (0.000005 if factor==0.00001 else (0.000001 if factor==0.000005 else (0.0000005 if factor==0.000001 else (0.0000001 if factor==0.0000005 else 0.00000001)))))))))))
                            _logger.info("factor: %s" % factor)
                        porcentaje -= factor
                        _logger.info("disminuye porcentaje: %s" % porcentaje)
                    else:
                        break
                        
                    for input_line in input_line_ids:
                        _logger.info("*** Actualizando Linea ***")
                        input_line['input_line'].write({'amount' : input_line['amount'] * (1.0 + porcentaje)})
                        _logger.info("input_line['input_line'].amount: %s" % input_line['input_line'].amount)
                    
                    lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                    monto_actual = sum(l[2]['amount'] if l[2]['code'] in ('NET','ASM_NETO') else 0.0 for l in lines)
                    if round(monto_actual - 0.01, 2) == round(monto_objetivo, 2):
                        input_line['input_line'].write({
                            'amount' : round(input_line['input_line'].amount - 0.01,2)
                        })
                        lines = [(0, 0, line) for line in self._get_payslip_lines(contract_ids, payslip.id)]
                    elif round(monto_actual + 0.01, 2) == round(monto_objetivo, 2):
                        input_line['input_line'].write({
                            'amount' : round(input_line['input_line'].amount + 0.01,2)
                        })
                        lines = [(0, 0, line) for line in self._get_payslip_lines(contract_ids, payslip.id)]
                                
            else:            
                lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                
            payslip.write({'line_ids': lines, 'state': 'verify', 'compute_date': fields.Date.today()})
        return True
    
    
    
    def get_cfdi_related(self):
        return False
    
    #@api.model
    def get_inputs(self):
        domain = [('employee_id','=',self.employee_id.id),
                  ('payslip_id','=',False), 
                  ('state','=','approved'),
                  ('date','<=',self.date_to)]
        if self.env.user.company_id.extras_dentro_de_periodo_de_nomina=='1' and not self.settlement_id:
            domain.append(('date','>=',self.date_from))
            
        extras = []
        for x in self.env['hr.payslip.extra'].search(domain): 
            ## No tomar Fonacot fuera den rango de la nomina para Finiquitos
            if self.settlement_id and x.hr_salary_rule_id.nomina_aplicacion=='deduccion' and \
                x.hr_salary_rule_id.id in self.company_id.\
                    reglas_a_incluir_en_periodo_de_nomina_finiquito_ids.ids and \
                    x.date > self.date_to:
                continue
            ## FIN: No tomar Fonacot fuera del rango de la nomina para Finiquitos
            extras.append((0,0,{'name'       : x.hr_salary_rule_id.name,
                           'code'       : x.hr_salary_rule_id.code,
                           'amount'     : x.amount,
                           'contract_id': self.contract_id.id,
                           'payslip_extra_id' : x.id,
                          }))
        return extras
    
    
    
    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return

        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to

        self.company_id = employee.company_id
        if not self.contract_id or self.employee_id != self.contract_id.employee_id: # Add a default contract if not already defined
            contracts = employee._get_contracts(date_from, date_to)
            
            if not contracts or not contracts[0].struct_id: #contracts[0].structure_type_id.default_struct_id:
                self.contract_id = False
                self.struct_id = False
                return
            self.contract_id = contracts[0]
            self.struct_id = contracts[0].struct_id
        
        payslip_name = self.struct_id.payslip_name or _('Salary Slip')
        self.name = '%s %s - %s - del %s al %s' % (_('Recibo'), self.struct_id.name, self.employee_id.name or '', self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y'))

        if date_to > date_utils.end_of(fields.Date.today(), 'month'):
            self.warning_message = _(
                "This payslip can be erroneous! Work entries may not be generated for the period from %(start)s to %(end)s.",
                start=date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1),
                end=date_to,
            )
        else:
            self.warning_message = False
        
        self.worked_days_line_ids = self._get_new_worked_days_lines()
        
        if not self.date_payroll:
            self.date_payroll = self.date_to
        self.input_line_ids = [(6,0,[])] # False
        self.input_line_ids = self.get_inputs()
        
        
        # Se agrega para revisar  que los factores entren en al periodo de la nomina
        uma = self.env['sat.nomina.uma_umi'].search([('tipo','=','uma'), ('vigencia','<=',self.date_to)], 
                                                    order='vigencia desc', limit=1)
        umi = self.env['sat.nomina.uma_umi'].search([('tipo','=','umi'), ('vigencia','<=',self.date_to)],
                                                    order='vigencia desc', limit=1)
        
        salario_minimo = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smg'), ('vigencia','<=',self.date_to)],
                                                                      order='vigencia desc', limit=1)
        salario_minimo_frontera_norte = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smfn'), ('vigencia','<=',self.date_to)],
                                                                                     order='vigencia desc', limit=1)
        
        self.salario_minimo = salario_minimo.id
        self.salario_minimo_fn = salario_minimo_frontera_norte.id
        self.uma = uma.id
        self.umi = umi.id
    

    ################################
    def do_something_with_xml_attachment(self, attach):
        return True
    
    @api.depends('neto_a_pagar')
    def _get_amount_to_text(self):
        currency = self.env.user.company_id.currency_id.name.upper()
        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = 'M.N' if currency == 'MXN' else 'M.E.'
        # Split integer and decimal part
        for rec in self:
            amount_i, amount_d = divmod(rec.neto_a_pagar, 1)
            amount_d = round(amount_d, 2)
            amount_d = int(amount_d * 100)
            words = rec.company_id.currency_id.with_context(lang=rec.employee_id.address_home_id.lang or 'es_ES').amount_to_text(amount_i).upper()
            invoice_words = '%(words)s %(amount_d)02d/100 %(curr_t)s' % dict(
                words=words, amount_d=amount_d, curr_t=currency_type)
            rec.amount_to_text = invoice_words
    


    
    def _get_fname_payslip(self):
        for slip in self:
            fname = slip.company_id.partner_id.vat or ''
            fname += '_' + (slip.number and slip.number.replace('/','_').replace(' ','') or '')
            slip.fname_payslip = fname 
        
    
    
    @api.depends('cfdi_state','state')
    def _get_uuid_from_attachment(self):
        attach_obj = self.env['ir.attachment']
        slip_obj = self.env['hr.payslip']
        for rec in self.filtered(lambda w: w.state not in ('draft','cancelled')):
            attachment_xml_ids = attach_obj.search([('res_model', '=', 'hr.payslip'), 
                                                    ('res_id', '=', rec.id), 
                                                    ('name', 'ilike', '.xml')], limit=1)
            if attachment_xml_ids:
                try:
                    xml_data = base64.b64decode(attachment_xml_ids.datas).replace('http://www.sat.gob.mx/cfd/3 ', '').replace('Rfc=','rfc=').replace('Fecha=','fecha=').replace('Total=','total=').replace('Folio=','folio=').replace('Serie=','serie=')
                    arch_xml = parseString(xml_data)
                    xvalue = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')[0]
                    timbre = xvalue.attributes['UUID'].value
                    res = slip_obj.search([('sat_uuid', '=', timbre),('id','!=',rec.id)])
                    if res:
                        raise UserError(_("Error ! El CFDI de Nómina ya se encuentra registrado en el sistema y no puede tener registro duplicado.\n\nEl CFDI de Nómina con Folio Fiscal %s se encuentra registrado con la Referencia: %s - ID: %s")%(timbre, res.name, res.id))
                    rec.sat_uuid = timbre
                except:
                    pass  
    


    @api.depends('contract_id','date_to')
    def _get_antiguedad(self): 
        for rec in self:
            if not rec.contract_id.fecha_ingreso or not rec.date_to:
                rec.antiguedad = ''
                return
            f1 = rec.contract_id.fecha_ingreso
            f2 = rec.date_to
            total_dias = (f2 - f1).days - 1
            anos = int(total_dias / 365)
            meses = int((((total_dias / 365) - anos) * 365) / 30)
            dias = total_dias - ((anos * 365) + (meses * 30))

            rec.antiguedad = 'P' + (anos and (str(anos) + 'Y') or '') + (meses and (str(meses) + 'M') or '') + (dias and (str(dias) + 'D') or '')
            rec.antiguedad_anios = anos
            _logger.info("total_dias: %s" % total_dias)
            if total_dias >= 7:
                rec.antiguedad = 'P' + str(int(total_dias/7)) + 'W'
            else:
                rec.antiguedad = 'P' + str(total_dias+2) + 'D'
    
    
    antiguedad_anios = fields.Integer(string="Antigüedad (Años)", compute="_get_antiguedad", store=False)
    antiguedad = fields.Char(string="Antigüedad", compute="_get_antiguedad", store=False)
    partner_id = fields.Many2one("res.partner", related="employee_id.address_home_id", readonly=True, index=True, store=True)
    sat_uuid = fields.Char(compute='_get_uuid_from_attachment', string="CFDI UUID", required=False, store=True, index=True)
        
    user_id = fields.Many2one('res.users', string='Usuario', readonly=True, default=lambda self: self.env.user)

    fname_payslip   =  fields.Char(compute='_get_fname_payslip', string='Nombre Archivo de Recibo de Nómina',
                                    help='Nombre del archivo a usar para los archivos XML y PDF del Recibo de Nómina CFDI')
    amount_to_text  = fields.Char(compute='_get_amount_to_text', string='Monto en Texto', store=True,
                                  help='Monto a pagar en letras')
    # Campos donde se guardara la info de CFDI    
    no_certificado  = fields.Char(string='No. Certificado', 
                                  help='Número de Certificado usado para generar el CFDI')
    certificado     = fields.Text('Certificado', help='Certificado usado para generar el CFDI')
    sello           = fields.Text('Sello', help='Sello Digital')
    cadena_original = fields.Text('Cadena Original', help='Cadena original con la información del CFDI') 
    
    cfdi_cbb               = fields.Binary(string='Imagen Código Bidimensional', readonly=True, copy=False)
    cfdi_sello             = fields.Text('Sello CFDI',  readonly=True, help='Sign assigned by the SAT', copy=False)
    cfdi_no_certificado    = fields.Char('No.Certificado', readonly=True,
                                       help='Serial Number of the Certificate', copy=False)
    cfdi_cadena_original   = fields.Text(string='Cadena Original.', readonly=True,
                                        help='Original String used in the electronic invoice', copy=False)
    cfdi_fecha_timbrado    = fields.Datetime(string='Fecha Timbrado', readonly=True,
                                           help='Fecha en que se obtiene el Timbrado del CFDI', copy=False)
    cfdi_fecha_cancelacion = fields.Datetime(string='Fecha Cancelación', readonly=True,
                                             help='Fecha cuando la factura es Cancelada', copy=False)
    cfdi_folio_fiscal      = fields.Char(string='Folio Fiscal (UUID)', size=64, readonly=True,
                                     help='Folio Fiscal del Comprobante CFDI, también llamado UUID', copy=False)

    cfdi_state              = fields.Selection([('draft','Pendiente'),
                                                ('xml_unsigned','XML a Timbrar'),
                                                ('xml_signed','Timbrado'),
                                                ('pdf','PDF'),
                                                ('sent', 'Correo enviado'),
                                                ('cancel','Cancelado'),
                                                ], string="Estado CFDI", readonly=True, default='draft',
                                     help='Estado del Proceso para generar el Comprobante Fiscal', copy=False)
    
    
    # PENDIENTE => Definir el metodo donde se usaran
    xml_file_no_sign_index  = fields.Text(string='XML a Timbrar', readonly=True, 
                                          help='Contenido del Archivo XML que se manda a Timbrar al PAC (con Complemento)', copy=False)
    xml_file_signed_index   = fields.Text(string='XML Timbrado', readonly=True, 
                                          help='Contenido del Archivo XML final (después de timbrado y Addendas)', copy=False)
    cfdi_last_message       = fields.Text(string='Último Mensaje', readonly=True, 
                                          help='Message generated to upload XML to sign', copy=False)
    xml_acuse_cancelacion   = fields.Text('XML Acuse Cancelacion', readonly=True)
    ################################
    # Proceso de Cancelacion de CFDI 2022
    cfdi_motivo_cancelacion = fields.Selection([
        ('01', '[01] Comprobantes emitidos con errores con relación'), # No se agrega como opción
        ('02', '[02] Comprobantes emitidos con errores sin relación'),
        ('03', '[03] No se llevó a cabo la operación'),
        ('04', '[04] Operación nominativa relacionada en una factura global')
    ], string="Motivo Cancelación", readonly=True)
    
    
    def get_max_date(self, vigencias):
        if not vigencias:
            return fields.Date.today()
        fechas = []
        for _w in vigencias:
            if _w.vigencia not in fechas:
                fechas.append(_w.vigencia)
        return max(fechas) # asumimos tipo de dato "date"
        
    
    @api.depends('date_to','payslip_run_id')
    def _get_tabla_isr(self):
        tabla_isr_obj = self.env['sat.nomina.tabla_isr']
        
        if self.payslip_run_id:            
            vigencias = tabla_isr_obj.search([("vigencia", "<=", self.payslip_run_id.date_end)])
            tabla = tabla_isr_obj.search([('vigencia','=',self.get_max_date(vigencias))])
            for rec in self:
                rec.tabla_isr = tabla
        else:
            for rec in self:
                vigencias = tabla_isr_obj.search([("vigencia", "<=", self.date_to)])
                tabla = tabla_isr_obj.search([('vigencia','=',self.get_max_date(vigencias))])
                rec.tabla_isr = tabla

        
    @api.depends('date_to','payslip_run_id')
    def _get_tabla_subsidio(self):
        tabla_subs_obj = self.env['sat.nomina.tabla_subsidio']
        if self.payslip_run_id:            
            vigencias = tabla_subs_obj.search([("vigencia", "<=", self.payslip_run_id.date_end)])
            tabla = tabla_subs_obj.search([('vigencia','=',self.get_max_date(vigencias))])
            for rec in self:
                rec.tabla_susidio = tabla
        else:
            for rec in self:
                vigencias = tabla_subs_obj.search([("vigencia", "<=", self.date_to)])
                tabla = tabla_subs_obj.search([('vigencia','=',self.get_max_date(vigencias))])
                rec.tabla_susidio = tabla

        
    @api.depends()
    def _get_factores_imss(self):
        for rec in self:
            rec.factores_imss = self.env['sat.nomina.factores_imss'].search([], order="sequence")

        
        
    @api.model
    def default_get(self, default_fields):        
        res = super(HRPayslip, self).default_get(default_fields)
        uma = self.env['sat.nomina.uma_umi'].search([('tipo','=','uma')],order='vigencia desc', limit=1)
        umi = self.env['sat.nomina.uma_umi'].search([('tipo','=','umi')],order='vigencia desc', limit=1)
        
        salario_minimo = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smg')],order='vigencia desc', limit=1)
        salario_minimo_frontera_norte = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smfn')],order='vigencia desc', limit=1)
        res.update({'salario_minimo': salario_minimo and salario_minimo.id or False,
                    'salario_minimo_fn' : salario_minimo_frontera_norte and salario_minimo_frontera_norte.id or False,
                    'uma'           : uma and uma.id or False,
                    'umi'           : umi and umi.id or False,
                   })
        
        return res
    
    
    def _get_time_zone(self):
        userstz = self.env.user.partner_id.tz
        a = 0
        if userstz:
            hours = timezone(userstz)
            fmt = '%Y-%m-%d %H:%M:%S %Z%z'
            today_now = datetime.now()
            loc_dt = hours.localize(datetime(today_now.year, today_now.month, today_now.day,
                                             today_now.hour, today_now.minute, today_now.second))
            timezone_loc = (loc_dt.strftime(fmt))
            diff_timezone_original = timezone_loc[-5:-2]
            timezone_original = int(diff_timezone_original)
            s = str(datetime.now(pytz.timezone(userstz)))
            s = s[-6:-3]
            timezone_present = int(s)*-1
            a = timezone_original + ((
                timezone_present + timezone_original)*-1)
        return a
    
    def server_to_local_timestamp(self, src_tstamp_str, src_format, dst_format, dst_tz_name,
            tz_offset=True, ignore_unparsable_time=True):

        if not src_tstamp_str:
            return False

        res = src_tstamp_str.replace(tzinfo=None)
        if src_format and dst_format:
            # find out server timezone
            server_tz = 'UTC' #self.get_server_timezone()
            dt_value = src_tstamp_str
            if tz_offset and dst_tz_name:
                try:
                    dst_tz = pytz.timezone(dst_tz_name)
                    dt_value2 = pytz.utc.localize(dt_value, is_dst=None).astimezone(dst_tz)
                except:
                    pass
            res = dt_value2.replace(tzinfo=None)
        _logger.info("res: %s" % res)
        return res    
    
    
    def get_xml_to_sign(self): # Este metodo se sobreescribe
        '''Creates and returns a dictionnary containing 'cfdi' if the cfdi is well created, 'error' otherwise.
        '''
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        version = '3.3'
        self.payslip_datetime = fields.datetime.now()
        module_obj = self.env['ir.module.module']
        module_l10n_mx_edi = module_obj.sudo().search([('state','=','installed'),('name','=','l10n_mx_edi')])
        module_l10n_mx_einvoice = module_obj.sudo().search([('state','=','installed'),('name','=','l10n_mx_einvoice')])
        values = self._get_cfdi_data_dict(module_l10n_mx_edi, module_l10n_mx_einvoice)

        if module_l10n_mx_edi:
            # -----------------------
            # Check the configuration
            # -----------------------
            # -Check certificate
            certificate_ids = company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            if not certificate_id:
                error_log.append(_('No valid certificate found'))

            # -Check PAC
            if pac_name:
                pac_test_env = company_id.l10n_mx_edi_pac_test_env
                pac_username = company_id.l10n_mx_edi_pac_username
                pac_password = company_id.l10n_mx_edi_pac_password
                if not pac_test_env and not (pac_username and pac_password):
                    error_log.append(_('No PAC credentials specified.'))
            else:
                error_log.append(_('No PAC specified.'))

            if error_log:
                return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

            # -Compute date and time of the invoice
            time_invoice = datetime.strptime(
                self.l10n_mx_edi_time_invoice, DEFAULT_SERVER_TIME_FORMAT).time()
            # -----------------------
            # Create the EDI document
            # -----------------------
            version = self.l10n_mx_edi_get_pac_version()

            # -Compute certificate data
            values['date'] = datetime.combine(
                fields.Datetime.from_string(self.date_invoice), time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
            values['certificate_number'] = certificate_id.serial_number
            values['certificate'] = certificate_id.sudo().get_data()[0]

            # -Compute cfdi
            if version == '3.2':
                cfdi = qweb.render(CFDI_TEMPLATE, values=values)
                node_sello = 'sello'
                with tools.file_open('l10n_mx_edi/data/%s/cfdi.xsd' % version, 'rb') as xsd:
                    xsd_datas = xsd.read()
            elif version == '3.3':
                cfdi = qweb.render('l10n_mx_payroll.cfdi33_nomina12', values=values)
                _logger.info("cfdi: %s" % cfdi)
                node_sello = 'Sello'
                attachment = self.env.ref('l10n_mx_edi.xsd_cached_cfdv33_xsd', False)
                xsd_datas = base64.b64decode(attachment.datas) if attachment else b''
            else:
                return {'error': _('Unsupported version %s') % version}

            # -Compute cadena
            invoice_obj = self.env['account.invoice']
            tree = invoice_obj.l10n_mx_edi_get_xml_etree(cfdi)
            cadena = invoice_obj.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
        
            tree = self.l10n_mx_edi_get_xml_etree(cfdi)
            cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
            tree.attrib[node_sello] = certificate_id.sudo().get_encrypted_cadena(cadena)

            # Check with xsd
            if xsd_datas:
                try:
                    with BytesIO(xsd_datas) as xsd:
                        _check_with_xsd(tree, xsd)
                except (IOError, ValueError):
                    _logger.info(
                        _('The xsd file to validate the XML structure was not found'))
                except Exception as e:
                    return {'error': (_('The cfdi generated is not valid') +
                                        create_list_html(str(e).split('\\n')))}

            return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}
        
        elif True or module_l10n_mx_einvoice:
            invoice_obj = self.env['account.invoice']
            if not self.journal_id.use_for_cfdi:
                return False
            context = self._context and dict(self._context.copy()) or {}
            context.update(self._get_file_globals())
            if 'error' in context: # Revisamos si se cargan los archivos del CSD necesarios para generar el Sello del CFDI
                self.message_post(body="Error al generar CFDI\n\n" + context['error'], 
                                  subtype='notification')
                return False
            cert_str = invoice_obj._get_certificate_str(context['fname_cer'])
            if not cert_str: # Validamos si el Certificado se cargo correctamente
                self.message_post(subject="Error al generar CFDI",
                                  body=_("Error en Certificado !!!\nNo puedo obtener el Certificado de Sello Digital para generar el CFDI. Revise su configuración."), 
                                  subtype='notification')
                return False
            cert_str = cert_str.replace('\n\r', '').replace('\r\n', '').replace('\n', '').replace('\r', '').replace(' ', '')
            noCertificado = self.journal_id.serial_number #invoice_obj._get_noCertificado(context['fname_cer'])
            if not noCertificado: # Validamos si el Numero de Certificado se cargo correctamente
                self.message_post(subject="Error al generar CFDI",
                                  body=_("Error !!!\n\nNo se pudo obtener el Número de Certificado de Sello Digital para generar el CFDI. Por favor revise la configuración del Diario de Pago"), 
                                  subtype='notification')
                return False
        
            values['certificate_number'] = noCertificado
            values['certificate'] = cert_str
            cfdi = qweb.render('l10n_mx_payroll.cfdi33_nomina12', values=values)
            tree = fromstring(cfdi)
            xml_data = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            
            (fileno_xml, fname_xml) = tempfile.mkstemp('.xml', 'odoo_' + '__nomina__')
            os.close(fileno_xml)
            fname_txt = fname_xml.replace('.','_') + '.txt'
            (fileno_sign, fname_sign) = tempfile.mkstemp('.txt', 'odoo_' + '__nomina_txt_md5__')
            os.close(fileno_sign)
            
            doc_xml = xml.dom.minidom.parseString(data_xml)
            doc_xml_full = doc_xml.toxml().encode('ascii', 'xmlcharrefreplace')
            data_xml2 = xml.dom.minidom.parseString(doc_xml_full)
            f = codecs.open(fname_xml, 'w','utf-8')
            data_xml2.writexml(f, indent='    ', addindent='    ', newl='\r\n', encoding='UTF-8')
            f.close()
            
            context.update({
                'fname_xml'  : fname_xml,
                'fname_txt'  : fname_txt,
                'fname_sign' : fname_sign,
            })
            
            context.update({'xml_prev':doc_xml_full})
            txt_str = invoice_obj.with_context(context)._xml2cad_orig()
            if not txt_str:
                self.message_post(subject="Error al generar CFDI",
                                  body="Error en la Cadena Original !!!\nNo puedo obtener la Cadena Original del Comprobante.\n"
                                       "Revise su configuración.", 
                                  subtype='notification')
                return False
            context.update({'cadena_original': txt_str})
            self.write({'cfdi_cadena_original':txt_str, 'no_certificado': noCertificado})
            sign_str = invoice_obj.with_context(context)._get_sello()
            nodeComprobante = data_xml2.getElementsByTagName("cfdi:Comprobante")[0]
            nodeComprobante.setAttribute("Sello", sign_str)
            data_xml = data_xml2.toxml('UTF-8')
            data_xml = data_xml.replace(b'<?xml version="1.0" encoding="UTF-8"?>', b'<?xml version="1.0" encoding="UTF-8"?>\n')
            return data_xml

        
        
    
    def get_cfdi(self):
        raise UserError(_("Aviso !\n\n Este módulo requiere que tenga instalada la Localización Mexicana de Argil o de Odoo\n\n"
                          " Si tiene la LM de Argil entonces debe tener instalado el módulo l10n_mx_payroll_argil\n\n"
                          " Si tiene la LM de Odoo entonces debe tener instalado el módulo l10n_mx_payroll_odoo"))
        return True

    
    
    def action_cancel(self):
        raise UserError(_("Aviso !\n\n Este módulo requiere que tenga instalada la Localización Mexicana de Argil o de Odoo\n\n"
                          " Si tiene la LM de Argil entonces debe tener instalado el módulo l10n_mx_payroll_argil\n\n"
                          " Si tiene la LM de Odoo entonces debe tener instalado el módulo l10n_mx_payroll_odoo"))
        return True

    
    
    def action_payslip_done(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))
        self.write({'state' : 'done'})
        self.mapped('payslip_run_id').action_close()        
        
        
        ################
        
        precision = self.env['decimal.precision'].precision_get('Payroll')

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).mapped('payslip_run_id')
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        payslips_to_post = payslips_to_post.filtered(lambda slip: slip.state == 'done' and not slip.move_id)

        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contract for these payslips has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no account journal defined on it.'))

        # Map all payslips by structure journal and pay slips month.
        # {'journal_id': {'month': [slip_ids]}}
        slip_mapped_data = {slip.struct_id.journal_id.id: {fields.Date().end_of(slip.date_to, 'month'): self.env['hr.payslip']} for slip in payslips_to_post}
        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][fields.Date().end_of(slip.date_to, 'month')] |= slip

        for journal_id in slip_mapped_data: # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]: # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                date = slip_date
                move_dict = {
                    'narration': '',
                    'ref': date.strftime('%B %Y'),
                    'journal_id': journal_id,
                    'date': date,
                }

                for slip in slip_mapped_data[journal_id][slip_date]:
                    _logger.info("Poliza contable para %s" % slip.number)
                    move_dict['narration'] += slip.number or '' + ' - ' + slip.employee_id.name or ''
                    move_dict['narration'] += '\n'
                    _logger.info("move_dict['narration']: %s" % move_dict['narration'])
                    for line in slip.line_ids.filtered(lambda line: line.category_id):
                        amount = -line.total if slip.credit_note else line.total
                        if line.code == 'NET': # Check if the line is the 'Net Salary'.
                            for tmp_line in slip.line_ids.filtered(lambda line: line.category_id):
                                if tmp_line.salary_rule_id.not_computed_in_net: # Check if the rule must be computed in the 'Net Salary' or not.
                                    if amount > 0:
                                        amount -= abs(tmp_line.total)
                                    elif amount < 0:
                                        amount += abs(tmp_line.total)
                        if float_is_zero(amount, precision_digits=precision):
                            continue
                        debit_account_id = line.salary_rule_id.account_debit.id
                        credit_account_id = line.salary_rule_id.account_credit.id

                        if debit_account_id: # If the rule has a debit account.
                            debit = amount if amount > 0.0 else 0.0
                            credit = -amount if amount < 0.0 else 0.0

                            existing_debit_lines = (
                                line_id for line_id in line_ids if
                                line_id['name'] == line.name
                                and line_id['account_id'] == debit_account_id
                                and line_id['analytic_account_id'] == (line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id)
                                and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0)))
                            debit_line = next(existing_debit_lines, False)

                            if not debit_line:
                                debit_line = {
                                    'name': line.name,
                                    'partner_id': line.partner_id.id,
                                    'account_id': debit_account_id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                                line_ids.append(debit_line)
                            else:
                                debit_line['debit'] += debit
                                debit_line['credit'] += credit
                        
                        if credit_account_id: # If the rule has a credit account.
                            debit = -amount if amount < 0.0 else 0.0
                            credit = amount if amount > 0.0 else 0.0
                            existing_credit_line = (
                                line_id for line_id in line_ids if
                                line_id['name'] == line.name
                                and line_id['account_id'] == credit_account_id
                                and line_id['analytic_account_id'] == (line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id)
                                and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0))
                            )
                            credit_line = next(existing_credit_line, False)

                            if not credit_line:
                                credit_line = {
                                    'name': line.name,
                                    'partner_id': line.partner_id.id,
                                    'account_id': credit_account_id,
                                    'journal_id': slip.struct_id.journal_id.id,
                                    'date': date,
                                    'debit': debit,
                                    'credit': credit,
                                    'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                }
                                line_ids.append(credit_line)
                            else:
                                credit_line['debit'] += debit
                                credit_line['credit'] += credit

                for line_id in line_ids: # Get the debit and credit sum.
                    debit_sum += line_id['debit']
                    credit_sum += line_id['credit']

                # The code below is called if there is an error in the balance between credit and debit sum.
                if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                    acc_id = slip.journal_id.default_credit_account_id.id
                    if not acc_id:
                        raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_credit = next(existing_adjustment_line, False)

                    if not adjust_credit:
                        adjust_credit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': 0.0,
                            'credit': debit_sum - credit_sum,
                        }
                        line_ids.append(adjust_credit)
                    else:
                        adjust_credit['credit'] = debit_sum - credit_sum

                elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                    acc_id = slip.journal_id.default_debit_account_id.id
                    if not acc_id:
                        raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (slip.journal_id.name))
                    existing_adjustment_line = (
                        line_id for line_id in line_ids if line_id['name'] == _('Adjustment Entry')
                    )
                    adjust_debit = next(existing_adjustment_line, False)

                    if not adjust_debit:
                        adjust_debit = {
                            'name': _('Adjustment Entry'),
                            'partner_id': False,
                            'account_id': acc_id,
                            'journal_id': slip.journal_id.id,
                            'date': date,
                            'debit': credit_sum - debit_sum,
                            'credit': 0.0,
                        }
                        line_ids.append(adjust_debit)
                    else:
                        adjust_debit['debit'] = credit_sum - debit_sum

                # Add accounting lines in the move
                move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                move = self.env['account.move'].create(move_dict)
                for slip in slip_mapped_data[journal_id][slip_date]:
                    slip.write({'move_id': move.id, 'date': date})
        ################
        for slip in self.filtered(lambda w: w.settlement_id):
            # Ponemos los descuentos de Fonacot "futuros" como Cancelados
            for line in slip.input_line_ids.filtered(lambda w: w.payslip_extra_id and \
                       w.payslip_extra_id.hr_salary_rule_id.id in slip.company_id.\
                       reglas_a_incluir_en_periodo_de_nomina_finiquito_ids.ids and \
                       w.payslip_extra_id.extra_discount_id):
                extras = line.payslip_extra_id.extra_discount_id.payslip_extra_ids.filtered(lambda w: w.state in ('draft','confirmed','approved') and w.date > slip.date_to)
                extras.action_cancel()
            # FIN: Ponemos los descuentos de Fonacot "futuros" como Cancelados
        self.get_cfdi()
        return True
    
    
    def action_payslip_cancel(self):
        if self.filtered(lambda slip: slip.state == 'done'):
            raise UserError(
                _('Cannot cancel a payslip that is done.')
            )
        self.write({'state': 'cancel', 'payslip_run_id' : False})
        return True
    
    def action_print_payslip(self):
        return {
            'name': 'Payslip',
            'type': 'ir.actions.act_url',
            'url': '/print/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
        }
    