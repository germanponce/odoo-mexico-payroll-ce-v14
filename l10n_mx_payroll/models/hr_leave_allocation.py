# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)
    
    
class HRLeavesAllocation(models.Model):
    _inherit = 'hr.leave.allocation'
    
    
    def _default_contract(self):
        employee =  self.env.context.get('default_employee_id') or\
                        self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee:
            return self.env['hr.contract'].search([('employee_id','=',employee.id),('state','=','open')],
                                                 order='date_start desc', limit=1)
        else:
            return False
    
    
    state = fields.Selection(selection_add=[('vencida', 'Vencida')])
    
    contract_id = fields.Many2one('hr.contract', string="Contrato", readonly=True,
                                  default=_default_contract, tracking=True,
                                  states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    vacaciones  = fields.Boolean(string="Son Vacaciones", index=True, 
                                 default=False, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    antiguedad  = fields.Integer(string="Antigüedad", required=True, default=0.0, 
                                 copy=False, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    vacaciones_vigencia_inicio  = fields.Date(string="Vacaciones Vigencia", index=True, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    vacaciones_vigencia_final   = fields.Date(string="Vacaciones Vigencia2", index=True, readonly=True,
                                 states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})

    company_id          = fields.Many2one('res.company', 'Compañía', 
                                          default=lambda self: self.env.company)
        
        
    @api.onchange('employee_id')
    def _onchange_employee(self):
        #res = super(HRLeavesAllocation, self)._onchange_employee()        
        if not self.employee_id or self.holiday_type != 'employee':
            self.contract_id = False
        elif self.employee_id:
            contract = self.env['hr.contract'].search([('employee_id','=',self.employee_id.id),('state','=','open')], limit=1, order='date_start desc')
            if contract:
                self.contract_id = contract.id
        
    
    # Metodo que se usa en el cron de Odoo
    def get_vacations(self, xdate=datetime.now().date(),
                      department_ids=False,
                      employee_ids=False):
        date = xdate
        leaves_allocation_obj = self.env['hr.leave.allocation']
        payroll_extra_obj = self.env['hr.payslip.extra']
        leaves = leaves_allocation_obj.browse([])
        manager = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        leave_status = self.env['hr.leave.type'].search([('name','=','VACACIONES')], limit=1)
        if not leave_status:
            raise UserError(_("Advertencia!\nNo existe el Tipo de Ausencia VACACIONES. Por favor revise su configuración..."))
        dominio = [('state','=','open')]
        if department_ids:
            dominio.append(('department_id','in',department_ids.ids))
        if employee_ids:
            dominio.append(('employee_id','in',employee_ids.ids))
            
        param_fecha_inicio = self.env.user.company_id.antiguedad_finiquito
                
        for contract in self.env['hr.contract'].search(dominio):
            fecha_ingreso = (contract.fecha_ingreso if param_fecha_inicio == 2 else contract.date_start)
            antig = xdate - fecha_ingreso
            _logger.info("====== [%s] %s =====" % (contract.id, contract.name))
            if antig.days/365 <= 0:
                _logger.info("Tiene menos de 1 anio de Antiguedad, No se genera Asignacion de Vacaciones")
                continue
            elif not (xdate.month==fecha_ingreso.month and xdate.day == fecha_ingreso.day):
                _logger.info("No tiene Aniversario en esta fecha, No se genera Asignacion de Vacaciones")
                continue
                
            empl_leaves = leaves_allocation_obj.search([('vacaciones','=',True),
                                             ('contract_id','=',contract.id),
                                             ('state','=','validate'),
                                             #('type','=','add'), 
                                             ('holiday_status_id','=',leave_status.id),
                                             ('vacaciones_vigencia_inicio','<=', xdate), 
                                             ('vacaciones_vigencia_final', '>=', xdate)])
            if empl_leaves: # Ya fueron creadas las vacaciones para este contrato
                continue
            # Se crean las vacaciones para el contrato
            anios = int(antig.days/365.0)
            if not anios:
                continue
            elif anios > 44:
                dias = 28
            else:
                xdias = self.env['sat.nomina.tabla_vacaciones'].search([('antiguedad','=',anios)])
                if not xdias:
                    raise UserError(_("Advertencia!\nNo existe el rango para Vacaciones\nTipo de Ausencia VACACIONES.\nPor favor revise su configuración..."))
                dias = xdias.dias
            
            data = {'holiday_status_id' : leave_status.id,
                    'employee_id'       : contract.employee_id.id,
                    'name'              : 'Trabajador: [' + str(contract.employee_id.id) + '] ' +\
                                            contract.employee_id.name +  ' - Contrato: ' +\
                                            contract.name + _(' Vacaciones'),
                    'contract_id'       : contract.id,
                    'number_of_days'    : dias,
                    'date_from'         : xdate,
                    'date_to'           : xdate + relativedelta(years=1,days=-1),
                    'vacaciones_vigencia_inicio' : xdate,
                    'vacaciones_vigencia_final'  : xdate + relativedelta(years=1,days=-1),
                    'state'             : 'draft',
                    'vacaciones'        : True,
                    'antiguedad'        : anios,
            }
            res = leaves_allocation_obj.create(data)
            leaves += res
            #
            if contract.company_id.crear_extra_prima_vacacional_en_aniversario=='1':
                data_extra = {'employee_id'       : contract.employee_id.id,
                              'hr_salary_rule_id' : contract.company_id.prima_vacacional_salary_rule_id.id,
                              'date'              : xdate + timedelta(days=contract.company_id.dias_despues_de_aniversario_para_pagar_prima_vacacional),
                              'qty'               : dias,
                           }
                extra = payroll_extra_obj.new(data_extra)
                extra.onchange_employee()
                data_extra = extra._convert_to_write(extra._cache)
                extra_rec = payroll_extra_obj.create(data_extra)
                extra_rec.action_confirm()
                extra_rec.action_approve()
        if leaves:
            leaves.action_confirm()
            leaves.action_validate()
            
        
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('hr_holidays.hr_leave_allocation_action_all')
        list_view_id = imd.xmlid_to_res_id('hr_holidays.hr_leave_allocation_view_tree')
        form_view_id = imd.xmlid_to_res_id('hr_holidays.hr_leave_allocation_view_form_manager')
        domain = "[('id','in', [" + ','.join(map(str, leaves.ids)) + "])]"
        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            #'context': self.env._context,
            'res_model': action.res_model,
            'domain'    : domain,
        }
    
    def _check_vacations_validity(self, xdate=datetime.now().date()):
        leave_status = self.env['hr.leave.type'].search([('name','=','VACACIONES')], limit=1)
        if not leave_status:
            raise UserError(_("Advertencia!\nNo existe el Tipo de Ausencia VACACIONES. Por favor revise su configuración..."))
        leave_alloc_obj = self.env['hr.leave.allocation']
        dias = self.env.user.company_id.dias_para_vencimiento_de_vacaciones
        fecha = xdate - timedelta(days=dias)
        
        for rec in leave_alloc_obj.search([('state','=','validate'),
                                           ('holiday_status_id','=',leave_status.id),
                                           ('vacaciones','=',True),
                                           ('vacaciones_vigencia_final','<=',fecha),
                                           ('holiday_type','=','employee'),
                                          ]):
            _logger.info("Vacaciones vencidas [%s] %s" % (rec.id, rec.display_name))
            rec.write({'state':'vencida'})
            rec.message_post(body=_("Esta Asignación de Vacaciones se pone como Vencida porque ya pasó del periodo de gracia de %s días") % dias, subtype='notification')
        return True
