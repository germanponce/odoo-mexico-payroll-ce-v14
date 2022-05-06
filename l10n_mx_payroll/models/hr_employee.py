# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from odoo.osv import expression
import logging
_logger = logging.getLogger(__name__)

class HREmployee(models.Model):
    _inherit = 'hr.employee'

    
    
    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.date_start', 'contract_ids.date_end')
    def _get_contrato_activo(self):
        ctx = self._context.copy()
        hoy = ctx.get('fecha') or datetime.now().date()
        for rec in self:            
            rec.con_contrato_activo = any([x.state=='open' and x.date_start <= hoy and \
                                             (x.date_end and x.date_end >= hoy or True) \
                                             for x in rec.contract_ids])
            
    
    
    def _search_get_contrato_activo(self, operator, value):
        ctx = self._context.copy()
        hoy = ctx.get('fecha') or datetime.now().date()

        contracts1 = self.env['hr.contract'].search([('date_start', '<=', hoy), ('date_end','=',False),
                                                     ('state','=','open')])
        contracts2 = self.env['hr.contract'].search([('date_start', '<=', hoy), ('date_end','!=',False),
                                                      ('date_end','>=',hoy), ('state','=','open')])
        contracts = contracts1 + contracts2
        
        if contracts:
            return [('id', 'in', [x.employee_id.id for x in contracts])]
        else:
            return [('id', 'in', [])]


    sdi_ids = fields.One2many('hr.contract.sdi','employee_id', 
                              string="Historial de SDIs", readonly=True)
    contract_sindicalizado = fields.Selection(related='contract_id.sindicalizado', store=True, index=True)
    contract_department_id = fields.Many2one('hr.department', string="Departamento (Contrato)",
                                             related="contract_id.department_id", store=True, index=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Estructura Salarial", 
                                related="contract_id.struct_id", store=True, readonly=True)
    con_contrato_activo = fields.Boolean(string="Tiene Contrato Activo", compute="_get_contrato_activo", 
                                         search="_search_get_contrato_activo", store=False)
    num_empleado= fields.Char(string="Número de Empleado")
    nss         = fields.Char(string="No. Seguro Social")
    curp        = fields.Char(string="CURP")
    
    infonavit_ids = fields.One2many('hr.employee.infonavit', 'employee_id', string="Infonavit")
    tipo_sangre = fields.Selection([('A+', 'A Positivo'),
                                    ('A-', 'A Negativo'),
                                    ('B+', 'B Positivo'),
                                    ('B-', 'B Negativo'),
                                    ('O+', 'O Positivo'),
                                    ('O-', 'O Negativo'),
                                    ('AB+', 'AB Positivo'),
                                    ('AB-', 'AB Negativo'),
                                    ], string="Tipo de Sangre")
    alergias    = fields.Char(string="Alergias")
    
    
    @api.onchange('num_empleado')
    def _onchange_num_empleado(self):
        self.registration_number = self.num_empleado
    
    
    def _get_contracts(self, date_from, date_to, states=['open'], kanban_state=False):
        """
        Returns the contracts of the employee between date_from and date_to
        """
        state_domain = [('state', 'in', states)]
        if kanban_state:
            state_domain = expression.AND([state_domain, [('kanban_state', 'in', kanban_state)]])

        return self.env['hr.contract'].search(
            expression.AND([[('employee_id', 'in', self.ids)],
            state_domain,
            [('date_start', '<=', date_to),
                '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', date_from)]]),
        order='employee_id, date_start desc')

class HREmployee_Infonavit(models.Model):
    _name = 'hr.employee.infonavit'
    _description = 'Infonavit por empleado'
    _order = "vigencia desc"

    name    = fields.Char('# Crédito', required=True)
    factor  = fields.Float('Factor/Monto', digits=(18,4), required=True)
    tipo    = fields.Selection([('veces_umi', 'Veces UMI'),
                                ('importe', 'Importe Fijo'),
                                ('porcentaje', 'Porcentaje (%)')],
                              string="Tipo de Cálculo", default='veces_umi', required=True)
    vigencia= fields.Date('Vigente desde', required=True)
    employee_id = fields.Many2one('hr.employee', string="Trabajador", required=True)
    
    _sql_constraints = [
        ('vigencia_unique', 'unique(employee_id, vigencia)','La vigencia debe ser única por trabajador')]
