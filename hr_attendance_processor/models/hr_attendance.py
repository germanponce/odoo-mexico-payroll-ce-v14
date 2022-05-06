# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import calendar
import pytz
import logging
_logger = logging.getLogger(__name__)


class HrAttendance_Processor_Wizard(models.TransientModel):
    _name = 'hr.attendance.processor_wiz'
    _description = "Wizard para procesar manualmente las Asistencias"
    
    date = fields.Date("Fecha a procesar", required=True)
    
    
    
    def attendance_processor(self):
        xdate = self.date
        res = self.env['hr.attendance'].check_attendances(xdate=xdate)
        return True
        


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    payslip_extra_id = fields.Many2one('hr.payslip.extra', string="Extra de Nómina", readonly=True)
    holiday_id       = fields.Many2one('hr.leave', string="Ausencia", readonly=True)
    retardo = fields.Boolean(string="Retardo", default=0,
                              help="Indica si este registro es un retardo", readonly=True)
    tomado_para_falta = fields.Boolean(string="Tomado para Falta", default=0,
                                       readonly=True,
                                       help="Indica si este registro ya fue tomado para generar una falta")
    
    falta   = fields.Boolean(string="Falta", default=0,
                              help="Indica si este registro es una Falta", readonly=True)
    
    
    
    procesado = fields.Boolean(string="Procesado", default=0,
                              help="Indica si este registro ya fue procesado", readonly=True)

    
    def check_attendances(self, xdate=False):
        tz = pytz.timezone(self.env.user.partner_id.tz or 'Mexico/General')
        tz_utc = pytz.timezone('UTC')
        contract_obj = self.env['hr.contract']
        payroll_extra_obj = self.env['hr.payslip.extra']
        holiday_obj = self.env['hr.leave']
        attend_obj = self.env['hr.attendance']
        
        dia_inicio_periodo_semanal = int(self.env.user.company_id.hr_attendance_dia_inicio_periodo_semanal)
        tolerancia_retardo = self.env.user.company_id.hr_attendance_minutos_tolerancia_retardo
        tolerancia_falta = self.env.user.company_id.hr_attendance_minutos_retardo_genera_falta
        tolerancia_hrs_extras = self.env.user.company_id.hr_attendance_minutos_tolerancia_hrs_extra
        tomar_tolerancia_hrs_extras = self.env.user.company_id.hr_attendance_hrs_extra_desde_tolerancia
        tolerancia_salida = self.env.user.company_id.hr_attendance_minutos_tolerancia_salida
        num_retardos_para_faltas = self.env.user.company_id.hr_attendance_retardos_para_una_falta
        considerar_retardos_en_mes = self.env.user.company_id.hr_attendance_considerar_retardos_en_periodo # 1
        retardo_x_minuto = self.env.user.company_id.hr_attendance_retardo_por_minuto
        retardo_x_minuto_salary_rule_id = self.env.user.company_id.hr_attendance_retardo_salary_rule_id.id # Concepto para Extra de retardo x Minuto
        _logger.info("== == == == == == == == == ==")
        _logger.info("Parámetros:")
        _logger.info("dia_inicio_periodo_semanal: %s" % dia_inicio_periodo_semanal)
        _logger.info("tolerancia_retardo: %s" % tolerancia_retardo)
        _logger.info("tolerancia_falta: %s" % tolerancia_falta)
        _logger.info("tolerancia_hrs_extras: %s" % tolerancia_hrs_extras)
        _logger.info("tomar_tolerancia_hrs_extras: %s" % tomar_tolerancia_hrs_extras)
        _logger.info("tolerancia_salida: %s" % tolerancia_salida)
        _logger.info("tolerancia_salida: %s" % tolerancia_salida)
        _logger.info("num_retardos_para_faltas: %s" % num_retardos_para_faltas)
        _logger.info("retardo_x_minuto: %s" % retardo_x_minuto)
        _logger.info("retardo_x_minuto_salary_rule_id: %s" % retardo_x_minuto_salary_rule_id)        
        _logger.info("== == == == == == == == == ==")

        

        regla_domingo_laborado = self.env['hr.salary.rule'].search([('name','=','* Día Festivo o Domingo Trabajado')], limit=1)

        if not regla_domingo_laborado:
            raise ValidationError(_('Advertencia !!!\nNo es posible procesar las Asistencias si no se encuentra definida la regla para Domingo Laborado como: \n"* Día Festivo o Domingo Trabajado"'))
            
        regla_faltas = self.env['hr.leave.type'].search([('name','=','FALTAS_INJUSTIFICADAS')], limit=1)

        if not regla_faltas:
            raise ValidationError(_('Advertencia !!!\nNo es posible procesar las Asistencias si no se encuentra definida el Tipo de Ausencia para las Faltas como: \n"FALTAS_INJUSTIFICADAS"'))
            
            
        regla_hrs_extra = self.env['hr.salary.rule'].search([('tipopercepcion_id.code','=','019'),
                                                             ('tipo_gravable','=','gravable')], limit=1)

        if not regla_hrs_extra:
            raise ValidationError(_('Advertencia !!!\nNo es posible procesar las Asistencias si no se encuentra definida el Tipo de Ausencia para las Faltas como: \n"FALTAS_INJUSTIFICADAS"'))        
            
        sat_tipohoraextra_doble = self.env['sat.nomina.tipohoraextra'].search([('code','=','01')], limit=1)

        if not sat_tipohoraextra_doble:
            raise ValidationError(_('Advertencia !!!\nNo es posible procesar las Asistencias si no se encuentra definida el Tipo de Hora Extra Dobles (Revise el Catálogo del SAT)'))        
        
        sat_tipohoraextra_triple = self.env['sat.nomina.tipohoraextra'].search([('code','=','02')], limit=1)

        if not sat_tipohoraextra_triple:
            raise ValidationError(_('Advertencia !!!\nNo es posible procesar las Asistencias si no se encuentra definida el Tipo de Hora Extra Triples (Revise el Catálogo del SAT)'))        
        
        today = xdate or (datetime.now() - timedelta(days=1)).date()
        
        ######
        if today.weekday()==dia_inicio_periodo_semanal:
            semana_inicio = today
        elif today.weekday() > dia_inicio_periodo_semanal:
            semana_inicio = today - timedelta(today.weekday() - dia_inicio_periodo_semanal)
        elif today.weekday() < dia_inicio_periodo_semanal:
            semana_inicio = today - timedelta(7 - (dia_inicio_periodo_semanal - today.weekday()))

        #########
        #semana_inicio = today - timedelta(today.weekday())
        semana_fin    = semana_inicio + timedelta(days=6)

        quincena_inicio = (date(today.year, today.month, 16) if today.day > 15 else date(today.year, today.month, 1))
        quincena_fin = (date(today.year, today.month, 15) if quincena_inicio==1 else (today + relativedelta(day=31)))

        
        today_from = datetime(today.year, today.month, today.day, 0,0,0)
        today_to = datetime(today.year, today.month, today.day, 23,59,59)
        attendance_domain = [('check_out','!=',False),
                             ('check_in', '>=', tz.localize(today_from).astimezone(pytz.utc)),
                             ('check_out','<=', tz.localize(today_to).astimezone(pytz.utc)),
                             ('procesado', '=', 0),
                            ]
        contract_with_attendance = contract_obj.browse([])
        # Checadas correctas
        attendance_ids = self.search(attendance_domain)
        # Checada de entrada sin checada de salida
        attendance_domain = [('check_out','=',False),
                             ('check_in', '>=', tz.localize(today_from).astimezone(pytz.utc)),
                             ('procesado', '=', 0),
                            ]
        attendance2_ids = self.search(attendance_domain)
        if attendance2_ids:
            attendance_ids += attendance2_ids
            
        for attendance in attendance_ids:
            try:
                if attendance.employee_id.company_id.id == self.env.user.company_id.id:
                    _logger.info("Procesando Asistencia de: %s" % attendance.employee_id.name)
                    _logger.info("Compañía: %s" % attendance.employee_id.company_id.name)
                else:
                    continue
            except:
                continue
            
            self._cr.execute("""select id from hr_contract
                             where state in ('open', 'pending') and date_start <= %s 
                             and (date_end is null or date_end >= %s)
                             and employee_id = %s
                             and company_id=%s limit 1;""",
                            [today.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'), 
                             attendance.employee_id.id, self.env.user.company_id.id])
            contract_id = [_x[0] for _x in self._cr.fetchall()]            
            if not contract_id:
                _logger.info(_('Trabajador sin Contrato Activo, por favor revise...'))
                continue
                
            contract = contract_obj.browse(contract_id)
            contract_with_attendance += contract
            if not contract.resource_calendar_id:
                _logger.info(_('Trabajador sin Horario de Trabajo definido, por favor revise...'))
                continue
            
            
            horario_entrada, horario_salida = False, False                
            for line in contract.resource_calendar_id.attendance_ids.filtered(lambda _q: int(_q.dayofweek)==today.weekday()):
                _logger.info("Linea: %s - dayofweek: %s - weekday: %s - %s - %s" % (line.name, line.dayofweek, today.weekday(), line.hour_from, line.hour_to))
                if not horario_entrada:
                    horario_entrada = datetime(today.year, today.month, today.day, 
                                               int(line.hour_from), int((line.hour_from - float(int(line.hour_from))) * 60), 0)
                horario_salida = datetime(today.year, today.month, today.day, 
                                          int(line.hour_to), int((line.hour_to - float(int(line.hour_to))) * 60), 0)

            if not(horario_entrada and horario_salida) and today.weekday() != 6:
                _logger.info(_('Trabajador sin Horario de Entrada y/o Salida para esta fecha, por favor revise...'))
                continue
            _logger.info("horario_entrada y horario_salida: %s - %s" % (horario_entrada, horario_salida))
            
            # Revisar si no estamos en periodo de Vacaciones o Incapacidad
            try:
                xres = holiday_obj.search([('employee_id','=', contract.employee_id.id),
                                           ('date_from', '<=', tz.localize(horario_entrada).astimezone(pytz.utc)),
                                           ('date_to','>=',tz.localize(horario_salida).astimezone(pytz.utc)),
                                           ('state','=','validate'),
                                          ])
            except:
                xres = False
            if xres:
                _logger.info("Trabajaror en Periodo de Vacaciones o Incapacidad")
                continue
            
            # Domingo laborado o día festivo
            if today.weekday() == 6 or \
                any(not _w.resource_id and _w.date_from <= attendance.check_in <= _w.date_to \
                    for _w in contract.resource_calendar_id.global_leave_ids): 
                data = {'employee_id'       : contract.employee_id.id,
                        'hr_salary_rule_id' : regla_domingo_laborado.id,
                        'date'              : today,
                       }
                extra = payroll_extra_obj.new(data)
                extra.onchange_employee()
                extra_data = extra._convert_to_write(extra._cache)
                try:
                    extra_rec = payroll_extra_obj.create(extra_data)
                    attendance.write({'payslip_extra_id' : extra_rec.id, 
                                      'procesado': True})
                except:
                    _logger.info(_("Error al crear Extra de Nómina para Domingo laborado o día festivo para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                    _logger.info("111 - extra_data: %s" % extra_data)
                    pass
            
            else: # No es domingo ni día festivo
                # Retardos
                horario_entrada, horario_salida = False, False                
                for line in contract.resource_calendar_id.attendance_ids.filtered(lambda _q: int(_q.dayofweek)==today.weekday()):
                    _logger.info("Linea: %s - dayofweek: %s - weekday: %s - %s - %s" % (line.name, line.dayofweek, today.weekday(), line.hour_from, line.hour_to))
                    if not horario_entrada:
                        horario_entrada = datetime(today.year, today.month, today.day, 
                                                   int(line.hour_from), int((line.hour_from - float(int(line.hour_from))) * 60), 0)
                    horario_salida = datetime(today.year, today.month, today.day, 
                                              int(line.hour_to), int((line.hour_to - float(int(line.hour_to))) * 60), 0)

                if not(horario_entrada and horario_salida):
                    _logger.info(_('Trabajador sin Horario de Entrada y/o Salida para esta fecha, por favor revise...'))
                    continue
                _logger.info("horario_entrada y horario_salida: %s - %s" % (horario_entrada, horario_salida))

                if considerar_retardos_en_mes == '1':
                    periodo_inicio = datetime(today.year, today.month, 1) # + ' 00:00:00'
                    periodo_final = datetime(today.year, today.month, calendar.monthrange(today.year, today.month)[1], 23, 59,59) 
                else:
                    if contract.schedule_pay == 'weekly':
                        periodo_inicio = semana_inicio # + ' 00:00:00'
                        periodo_final = semana_fin #+ ' 23:59:59'
                    elif contract.schedule_pay == 'bi-weekly':
                        periodo_inicio = quincena_inicio #+ ' 00:00:00'
                        periodo_final = quincena_fin #+ ' 23:59:59'
                    else:
                        _logger.info("Trabajador no tiene definido periodo Semanal y/o Quincenal")
                        continue
                _logger.info("attendance.check_in: %s" % attendance.check_in)
                _logger.info("horario_entrada + timedelta(minutes=tolerancia_retardo): %s" % (horario_entrada + timedelta(minutes=tolerancia_retardo)))
                check_in = attendance.check_in.replace(tzinfo=pytz.utc).\
                            astimezone(pytz.timezone(self.env.user.partner_id.tz or 'Mexico/General')).\
                            replace(tzinfo=None)                            
                _logger.info("check_in: %s" % check_in)
                if attendance.check_out:
                    check_out = attendance.check_out.replace(tzinfo=pytz.utc).\
                                astimezone(pytz.timezone(self.env.user.partner_id.tz or 'Mexico/General')).\
                                replace(tzinfo=None)
                else:
                    check_out = horario_salida # En caso de que solo haya registrado entrada.
                _logger.info("check_out: %s" % check_out)
                
                # CHECAMOS LA ENTRADA # retardo_x_minuto and 
                if check_in > horario_entrada: # El empleado registro entrada despues de su horario 
                    # Entrada posterior a Tolerancia ("n" minutos) la cual genera Falta
                    if check_in > horario_entrada + timedelta(minutes=tolerancia_falta): 
                        _logger.info("*** Revisando Falta por entrada Retardada (No solo por retardo)")
                        data = {'employee_id'       : contract.employee_id.id,
                                'holiday_status_id' : regla_faltas.id,
                                'date_from'         : tz.localize(horario_entrada).astimezone(pytz.utc).\
                                    replace(tzinfo=None),
                                'date_to'           : tz.localize(horario_salida).astimezone(pytz.utc).\
                                    replace(tzinfo=None),
                                'request_date_from' : horario_entrada.date(),
                                'request_date_to'   : horario_entrada.date(),
                                'holiday_type'      : 'employee',
                                'report_note'       : _('Falta por llegada después del tiempo máximo permitido'),
                               }
                        holiday = holiday_obj.new(data)
                        holiday._onchange_employee_id()
                        holiday._onchange_leave_dates()
                        holiday_data = holiday._convert_to_write(holiday._cache)
                        holiday_data['holiday_status_id'] = regla_faltas.id
                        _logger.info("111 - holiday_data: %s" % holiday_data)
                        try:
                            holiday_rec = holiday_obj.create(holiday_data)
                            attendance.write({'holiday_id'  : holiday_rec.id, 
                                              'procesado'   : True, 
                                              'retardo'     : True,
                                              'falta'       : True,
                                              'tomado_para_falta' : True,})                        
                        except:
                            _logger.info(_("Error al crear Ausencia para -Falta por Llegada Tardía- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                            pass
                    # Descuento por retardo por minutos 
                    elif contract.struct_id.aplica_descuento_x_minuto_retardo and \
                        retardo_x_minuto == '1' and \
                        (not contract.struct_id.crear_faltas_x_acumulacion_retardos or \
                         (contract.struct_id.crear_faltas_x_acumulacion_retardos and \
                          check_in <= horario_entrada + timedelta(minutes=tolerancia_retardo))): # Llega tarde pero antes de la Tolerancia para retardo
                        minutos_de_retraso = round((check_in - horario_entrada).seconds / 60.0, 0)
                        data = {'employee_id'       : contract.employee_id.id,
                                'hr_salary_rule_id' : retardo_x_minuto_salary_rule_id,
                                'date'              : today,
                                'qty'               : minutos_de_retraso,
                                   }
                        extra = payroll_extra_obj.new(data)
                        extra.onchange_employee()
                        data_extra = extra._convert_to_write(extra._cache)
                        data_extra.update({'qty'    : minutos_de_retraso,
                                           'amount' : (contract.cfdi_sueldo_base / 8.0 / 60.0) * minutos_de_retraso})
                        try:
                            extra_rec_dobles = payroll_extra_obj.create(data_extra)
                        except:
                            _logger.info(_("Error al crear Extra para - Minutos de retraso en Entrada para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                            _logger.info("XXX - data: %s" % data_extra)
                            pass
                    
                    # Retardos que al acumular "n" retardos genera una falta en el periodo
                    elif check_in > horario_entrada + timedelta(minutes=tolerancia_retardo) and \
                        contract.struct_id.crear_faltas_x_acumulacion_retardos: # Retardo
                        _logger.info("*** Retardos ***")
                        _logger.info("periodo_inicio: %s" % periodo_inicio)
                        _logger.info("periodo_final + timedelta(hours=23,minutes=59): %s" % (periodo_final + timedelta(hours=23,minutes=59)))
                        data_ids = attend_obj.search([('employee_id','=',attendance.employee_id.id),
                                                 ('check_in', '>=',periodo_inicio),
                                                 ('check_out','<=',periodo_final + timedelta(hours=23,minutes=59)),
                                                 ('retardo','=',1),
                                                 ('tomado_para_falta','!=', 1)])

                        _logger.info("data_ids: %s" % data_ids)
                        _logger.info("len(data_ids.ids): %s" % len(data_ids.ids))
                        if len(data_ids.ids) == (num_retardos_para_faltas - 1) and \
                            contract.struct_id.crear_faltas_x_acumulacion_retardos: # Es el "n" retardo segun parametro
                            data = {'employee_id'       : contract.employee_id.id,
                                    'holiday_status_id' : regla_faltas.id,
                                    'date_from'         : tz.localize(horario_entrada).astimezone(pytz.utc).\
                                    replace(tzinfo=None),
                                    'date_to'           : tz.localize(horario_salida).astimezone(pytz.utc).\
                                    replace(tzinfo=None),
                                    'request_date_from' : horario_entrada.date(),
                                    'request_date_to'   : horario_entrada.date(),
                                    'holiday_type'      : 'employee',
                                    'report_note'       : _('Falta por %s retardos en el periodo') % num_retardos_para_faltas,
                                   }
                            holiday = holiday_obj.new(data)
                            holiday._onchange_employee_id()
                            holiday._onchange_leave_dates()
                            holiday_data = holiday._convert_to_write(holiday._cache)
                            holiday_data['holiday_status_id'] = regla_faltas.id
                            _logger.info("222 - holiday_data: %s" % holiday_data)
                            try:
                                holiday_rec = holiday_obj.create(holiday_data)
                                attendance.write({'holiday_id'  : holiday_rec.id, 
                                                  'procesado'   : True, 
                                                  'retardo'     : True,
                                                  'falta'       : True,})
                                attendances_retardo = attend_obj.browse(data_ids.ids + [attendance.id])
                                attendances_retardo.write({'tomado_para_falta' : True})
                            except:
                                _logger.info(_("Error al crear Ausencia para -Falta por 3 Retardos en el periodo- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                                pass
                        else:
                            attendance.write({'procesado' : True, 'retardo' : True,})

                
                else:
                    attendance.write({'procesado' : True,})
                
                #Checamos checada de Salida previa al Horario de Salida
                if attendance.check_out and check_out < horario_salida - timedelta(minutes=tolerancia_salida): # 
                    # Crear la falta
                    data = {'employee_id'       : contract.employee_id.id,
                            'holiday_status_id' : regla_faltas.id,
                            'date_from'         : tz.localize(horario_entrada).astimezone(pytz.utc).\
                                replace(tzinfo=None),
                            'date_to'           : tz.localize(horario_salida).astimezone(pytz.utc).\
                                replace(tzinfo=None),
                            'request_date_from' : horario_entrada.date(),
                            'request_date_to'   : horario_entrada.date(),
                            'holiday_type'      : 'employee',
                            'report_note'       : _('Falta por Salida previa al Horario de Salida'),
                           }
                    holiday = holiday_obj.new(data)
                    holiday._onchange_employee_id()
                    holiday._onchange_leave_dates()
                    holiday_data = holiday._convert_to_write(holiday._cache)
                    holiday_data['holiday_status_id'] = regla_faltas.id
                    _logger.info(" 333 - holiday_data: %s" % holiday_data)
                    try:
                        holiday_rec = holiday_obj.create(holiday_data)
                        attendance.write({'holiday_id'  : holiday_rec.id, 
                                          'procesado'   : True, 
                                          'retardo'     : True,
                                          'falta'       : True,
                                          'tomado_para_falta' : True,})
                    except:
                        _logger.info(_("Error al crear Ausencia para -Salida previa al Horario de Salida- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                        pass
                # CHECAMOS LA SALIDA (HORAS EXTRAS)
                elif attendance.check_out and check_out > horario_salida + timedelta(minutes=tolerancia_hrs_extras): # Tolerancia para tomar Horas Extras
                    _logger.info("-- -- -- -- -- -- -- --")
                    _logger.info("*** Horas Extras ***")
                    _logger.info("attendance.check_out: %s" % attendance.check_out)
                    _logger.info("check_out: %s" % check_out)
                    _logger.info("horario_salida: %s" % horario_salida)
                    _logger.info("horario_salida + timedelta(minutes=tolerancia_hrs_extras): %s" % (horario_salida + timedelta(minutes=tolerancia_hrs_extras)))
                    _logger.info("domain: %s" %  [('employee_id','=',attendance.employee_id.id),
                                                          ('date', '>=',periodo_inicio),
                                                          ('date','<=',periodo_final),
                                                          ('state','=','approved')])
                    extra_ids = payroll_extra_obj.search([('employee_id','=',attendance.employee_id.id),
                                                          ('date', '>=',periodo_inicio),
                                                          ('date','<=',periodo_final),
                                                          ('state','=','approved')])
                    hrs_dobles, hrs_triples = 0, 0
                    for extra in extra_ids:
                        if extra.hr_salary_rule_id and \
                            extra.hr_salary_rule_id.tipopercepcion_id and \
                            extra.hr_salary_rule_id.tipopercepcion_id.code=='019':
                            hrs_dobles  += extra.qty if extra.sat_nomina_tipohoraextra_id.code=='01' else 0.0
                            hrs_triples += extra.qty if extra.sat_nomina_tipohoraextra_id.code=='02' else 0.0
                    
                    dobles, triples = 0, 0
                    dobles_disponibles = 9 - hrs_dobles
                    hsalida = (horario_salida + timedelta(minutes=tolerancia_hrs_extras)) if tomar_tolerancia_hrs_extras=='1' else horario_salida
                    hsalida = horario_salida
                    _logger.info("horario_salida: %s" % horario_salida)
                    _logger.info("check_out: %s" % check_out)
                    _logger.info("hsalida: %s" % hsalida)

                    horas = round((check_out - hsalida).seconds  / 60.0 / 60.0)
                    _logger.info("horas: %s" % horas)
                    _logger.info("dobles_disponibles: %s" % dobles_disponibles)
                    if (dobles_disponibles - (horas if horas <=3 else 3)) > 0:
                        
                        if horas <= 3:
                            dobles = horas
                        else:
                            dobles = 3
                            triples = horas - 3
                    else:
                        dobles = dobles_disponibles
                        triples = horas - dobles
                    
                    _logger.info("dobles: %s" % dobles)
                    _logger.info("triples: %s" % triples)
                    if dobles:
                        data = {'employee_id'       : contract.employee_id.id,
                                'hr_salary_rule_id' : regla_hrs_extra.id,
                                'date'              : today,
                                'sat_nomina_tipohoraextra_id' : sat_tipohoraextra_doble.id,
                                'qty'               : dobles,
                               }
                        extra = payroll_extra_obj.new(data)
                        extra.onchange_employee()
                        try:
                            extra_rec_dobles = payroll_extra_obj.create(extra._convert_to_write(extra._cache))
                        except:
                            _logger.info(_("Error al crear Extra para -Horas Extras Dobles- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                            _logger.info("222 - data: %s" % data)
                            pass
                        
                    if triples:
                        data = {'employee_id'       : contract.employee_id.id,
                                'hr_salary_rule_id' : regla_hrs_extra.id,
                                'date'              : today,
                                'sat_nomina_tipohoraextra_id' : sat_tipohoraextra_triple.id,
                                'qty'               : triples,
                               }
                        extra = payroll_extra_obj.new(data)
                        extra.onchange_employee()
                        try:
                            extra_rec = payroll_extra_obj.create(extra._convert_to_write(extra._cache))
                        except:
                            _logger.info(_("Error al crear Extra para -Horas Extras Triples- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                            _logger.info("333 - data: %s" % data)
                            pass
                    try:
                        attendance.write({'payslip_extra_id' : dobles and extra_rec_dobles.id or False, 
                                          'procesado': True})
                    except:
                        pass
                    _logger.info("*** FIN - Horas Extras ***")
                        
        _logger.info(" A A A A A  A A A A A A A  ")
                    
        self._cr.execute("""select id from hr_contract
                             where state in ('open', 'pending') and date_start <= %s 
                             and (date_end is null or date_end >= %s)
                             and company_id=%s;""",
                            [today.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'), self.env.user.company_id.id])
        contract_ids = [_x[0] for _x in self._cr.fetchall()]
        contracts = contract_obj.browse(contract_ids)
        contracts_wo_attendance = contracts - contract_with_attendance
        employees = []        
        for contract in contracts_wo_attendance:
            _logger.info("Procesando contrato: %s - %s" % (contract.id, contract.employee_id.name))
            if contract.employee_id.id in employees:
                _logger.info("Empleado ya procesado previamente...")
                continue
            if contract.employee_id.no_revisar_asistencia:
                _logger.info("Empleado marcado que no se revisen sus asistencias...")
                continue
            employees.append(contract.employee_id.id)
            horario_entrada, horario_salida = False, False
            for line in contract.resource_calendar_id.attendance_ids.filtered(lambda _q: int(_q.dayofweek)==today.weekday()):
                if not horario_entrada:
                    horario_entrada = datetime(today.year, today.month, today.day, 
                                               int(line.hour_from), int((line.hour_from - float(int(line.hour_from))) * 60), 0)
                horario_salida = datetime(today.year, today.month, today.day, 
                                          int(line.hour_to), int((line.hour_to - float(int(line.hour_to))) * 60), 0)
            
            if not(horario_entrada and horario_salida):
                _logger.info(_('Trabajador sin Horario de Entrada y/o Salida para esta fecha, por favor revise...'))
                continue
            
            #Revisamos si es dia festivo:
            x_horario_entrada = (horario_entrada + timedelta(minutes=15))
            if any(not _w.resource_id and \
                   _w.date_from <= x_horario_entrada <= _w.date_to \
                    for _w in contract.resource_calendar_id.leave_ids):
                _logger.info("\nEs dia festivo, no se revisan asistencias...")
                continue
            
            
            # Revisar si no estamos en periodo de Vacaciones o Incapacidad
            xres = holiday_obj.search([('employee_id','=', contract.employee_id.id),
                                       ('date_from', '<=', tz.localize(horario_entrada).astimezone(pytz.utc)), 
                                       ('date_to','>=',tz.localize(horario_salida).astimezone(pytz.utc)), 
                                       ('state','=','validate'),
                                      ])
            if xres:
                _logger.info("Trabajador en Periodo de Vacaciones o Incapacidad")
                continue
            # # # # # #
            
            data = {'employee_id'       : contract.employee_id.id,
                    'holiday_status_id' : regla_faltas.id,
                    'date_from'         : tz.localize(horario_entrada).astimezone(pytz.utc).\
                                replace(tzinfo=None),
                    'date_to'           : tz.localize(horario_salida).astimezone(pytz.utc).\
                                replace(tzinfo=None),
                    'request_date_from' : horario_entrada.date(),
                    'request_date_to'   : horario_entrada.date(),
                    'holiday_type'      : 'employee',
                    'report_note'       : _('Falta por no encontrar registro de Asistencia'),
                   }
            holiday = holiday_obj.new(data)
            holiday._onchange_employee_id()
            holiday._onchange_leave_dates()
            holiday_data = holiday._convert_to_write(holiday._cache)
            holiday_data['holiday_status_id'] = regla_faltas.id
            _logger.info("444 - holiday_data: %s" % holiday_data)
            try:
                holiday_rec = holiday_obj.create(holiday_data)
            except:
                _logger.info(_("Error al crear Ausencia por -Sin Registro de Asistencia- para: [%s] %s") % (contract.employee_id.id, contract.employee_id.name))
                pass

        _logger.info("------- FIN DE PROCESAMIENTO DE ASISTENCIAS --------")
        return True

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    
