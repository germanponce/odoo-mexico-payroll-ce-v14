# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta
import math
import logging
_logger = logging.getLogger(__name__)


class hr_employee_imss_crea_movimientos(models.TransientModel):
    _name = 'hr.employee.imss.movimientos.wizard'
    _description = "Asistente para crear Incidencias del IMSS"
    
    
    struct_type_ids = fields.Many2many('hr.payroll.structure.type',
                                  'hr_structure_type_mov_wizard_rel',
                                  'wizard_id', 'struct_type_id',
                                 string="Tipo de Estructura de Pago", required=True)
    
    struct_ids = fields.Many2many('hr.payroll.structure',
                                  'hr_structure_mov_wizard_rel',
                                  'wizard_id', 'struct_id',
                                 string="Estructura de Pago")
    
    department_ids = fields.Many2many('hr.department', string="Departamentos")
    
    employee_ids = fields.Many2many('hr.employee', string="Empleados")
    
    
    date_to = fields.Date(string='Hasta', required=True,
                          default=lambda self: fields.Date.to_string(date.today()))
    date_from = fields.Date(
        string='Desde', required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(days=-7)).date()))
    
    
    type = fields.Selection([('08', 'Alta o Reingreso'),
                             ('02','Baja'),
                             ('07', 'Modificación')
                            ], string="Tipo de Movimiento",
                            default='08',
                            required=True)
    
    
    def create_records(self):
        contract_obj = self.env['hr.contract']
        employee_imss_obj = self.env['hr.employee.imss']
        
        
        domain = []
        if self.struct_type_ids:
            domain.append(('structure_type_id','in',self.struct_type_ids.ids))
        if self.struct_ids:
            domain.append(('struct_id','in',self.struct_ids.ids))
        if self.department_ids:
            domain.append(('department_id','in',self.department_ids.ids))
        if self.employee_ids:
            domain.append(('employee_id','in',self.employee_ids.ids))
        #elif self.contract_ids:
        #    domain.append(('id','in',self.contract_ids.ids))
        
        
        if self.type=='08': # Altas o Reingresos
            domain.append(('fecha_ingreso','>=',self.date_from))
            domain.append(('fecha_ingreso','<=',self.date_to))
        elif self.type=='02': #Bajas
            domain.append(('date_end','>=',self.date_from))
            domain.append(('date_end','<=',self.date_to))
            settlements = self.env['hr.settlement'].search([('state','=','done'),
                                                            ('date','>=',self.date_from),
                                                            ('date','<=',self.date_to)])
            if settlements:
                settl_contracts = [x.contract_id.id for x in settlements]
                domain.append(('id', 'in', settl_contracts))
            
        else: # Modificacion - 07
            domain.append(('fecha_ingreso_vs_date_start','!=',True))
            domain.append(('date_start','>=',self.date_from))
            domain.append(('date_start','<=',self.date_to))
        
        
        _logger.info("domain: %s" % domain)
        contracts = contract_obj.search(domain)
        _logger.info("contracts: %s" % contracts)
        if not contracts:
            raise ValidationError(_('Advertencia! No se encontraron registros que coincidan con los filtros definidos'))
            
        data = {'date'  : self.date_to,
                'date_from' : self.date_from,
                'date_to' : self.date_to,
                'type'  : self.type,
                'contract_ids' : [(6,0, contracts.ids)]}
        

        mov = employee_imss_obj.new(data)
        mov._onchange_contract_ids()
        mov_data = mov._convert_to_write(mov._cache)
        mov_id = employee_imss_obj.create(mov_data)
        
        if self.type=='08': # Altas o Reingresos
            action = self.env.ref('l10n_mx_payroll_imss.action_hr_employee_imss_alta').read()[0]
        elif self.type=='02': #Bajas
            action = self.env.ref('l10n_mx_payroll_imss.action_hr_employee_imss_baja').read()[0]
        else: # Modificacion - 07
            action = self.env.ref('l10n_mx_payroll_imss.action_hr_employee_imss_modif').read()[0]
            
        form_view = [(self.env.ref('l10n_mx_payroll_imss.hr_employee_imss_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
        else:
            action['views'] = form_view
        action['res_id'] = mov_id.id
        
        return action
        
        
        