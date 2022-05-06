# -*- encoding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)



class HRPayslipExtraDiscounts(models.Model):
    _name = 'hr.payslip.extra.discounts'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Descuentos programados'
    
    
    
    @api.depends('payslip_extra_ids','payslip_extra_ids.state','state')
    def _get_saldo(self):
        for rec in self:
            if rec.state in ('draft','cancel'):
                rec.saldo = 0
            else:
                rec.saldo = rec.monto_total - sum(rec.payslip_extra_ids.filtered(lambda w: w.state=='done' and w.payslip_id.state!='cancel').mapped('amount'))
    
    name    = fields.Char(string="Referencia", required=True, readonly=True, index=True, default='/')
    description = fields.Char(string="Descripción", required=True, tracking=True,
                              readonly=True, states={'draft': [('readonly', False)]})
    date    = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, index=True, 
                          readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    date_start = fields.Date(string="Primer Descuento", required=True,
                             readonly=True, states={'draft': [('readonly', False)]},
                             help="Fecha en que se hará el primer descuento",
                             default=fields.Date.context_today)
    state   = fields.Selection([('draft','Borrador'),
                                ('progress', 'En Proceso'),
                                ('done', 'Realizado'),
                                ('cancel', 'Cancelado')],
                               string='Estado', default='draft', 
                               index=True, tracking=True)
    
    employee_id         = fields.Many2one('hr.employee', string='Empleado', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]}, index=True, tracking=True)
    
    contract_id         = fields.Many2one('hr.contract', string='Contrato', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]})
    department_id       = fields.Many2one('hr.department', related="contract_id.department_id", 
                                          readonly=True, store=True)    
    sat_periodicidadpago_id = fields.Many2one('sat.nomina.periodicidadpago', string="·Periodicidad Pago", 
                                              readonly=True,
                                              related="contract_id.sat_periodicidadpago_id")
    salary_rule_id   = fields.Many2one('hr.salary.rule', string='Concepto', required=True, 
                                       readonly=True,
                                       states={'draft': [('readonly', False)]}, index=True, 
                                       domain=[('can_be_payroll_extra','=',True)],
                                       tracking=True)

    saldo           = fields.Float("Saldo", digits=(16,2), compute="_get_saldo", store=True)
    
    monto_total     = fields.Float("Total a Descontar", digits=(16,2), required=True, default=0.0,
                                   readonly=True, states={'draft': [('readonly', False)]})
    monto_periodo   = fields.Float("Descuento por Nómina", digits=(16,2), required=True, default=0.0,
                                  readonly=True, states={'draft': [('readonly', False)]})
    
    aplicacion      = fields.Selection([('each', 'En Cada Nómina'),
                                        ('next', 'TODO en próxima nómina'),
                                        ('manual', 'Manual')],
                                       string="Forma de Descuento",
                                       readonly=True, states={'draft': [('readonly', False)]},
                                       required=True, default='each', index=True)
    
    payslip_extra_ids = fields.One2many('hr.payslip.extra', 'extra_discount_id', 
                                        string="Líneas de Descuento")
    notes             = fields.Text(string="Observaciones")
    company_id          = fields.Many2one('res.company', string='Compañía', 
                                          default=lambda self: self.env.company)
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if not self.employee_id:
            self.contract_id = False
        else:
            contract = self.env['hr.contract'].search([('employee_id','=',self.employee_id.id),('state','=','open')], limit=1, order='date_start desc')
            if contract:
                self.contract_id = contract.id
        return
    
    
    @api.constrains('monto_total','payslip_extra_ids')
    def _check_sum_amount(self):
        for rec in self:
            x = sum([w.amount for w in rec.payslip_extra_ids])
            if rec.state=='draft' and x and x != rec.monto_total:
                raise UserError(_('Error !\nEl Monto Total no cuadra con la sumatoria de las Líneas.'))
    
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('hr.payslip.extra.discounts') or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.payslip.extra.discounts') or '/'
        return super(HRPayslipExtraDiscounts, self).create(vals)
    
    
    
    def action_compute(self):
        self.ensure_one()
        self.payslip_extra_ids.action_cancel()
        self.payslip_extra_ids.write({'extra_discount_id':False})
        line_obj = self.env['hr.payslip.extra'].with_context(mail_create_nosubscribe=True)
        monto_total = self.monto_total
        monto_periodo = self.monto_periodo
        date_start = self.date_start
        flag = True
        _logger.info("self.contract_id.schedule_pay: %s" % self.contract_id.schedule_pay)
        dias = self.contract_id.sat_periodicidadpago_id.dias or 0.0
        if not dias:
            raise UserError(_("Advertencia!\nNo es posible calcular las líneas de descuento "
                              "si el periodo no corresponde a lo siguientes opciones:"
                              "* Diario"
                              "* Semanal"
                              "* Decenal"
                              "* Catorcenal"
                              "* Quincenal"
                              "* Mensual"
                              "* Bimestral"
                              "Para cualquier otro tipo de periodo es necesario capturar manualmente las Línas de Descuento"))
        data = {'employee_id'   : self.employee_id.id,
                'contract_id'   : self.contract_id.id,
                'hr_salary_rule_id' : self.salary_rule_id.id,
                'qty'           : 1.0,
                'extra_discount_id' : self.id,
                'company_id'    : self.env.user.company_id.id,
               }
        if self.aplicacion=='each':
            while monto_total >= 0.01: 
                if monto_total >= monto_periodo:
                    data['amount'] = monto_periodo
                    monto_total -= monto_periodo 
                else:
                    data['amount'] = monto_total
                    monto_total = 0            
                if flag:
                    data['date'] = date_start
                    flag = False
                else:
                    if round(dias, 1)==30.4:
                        date_start += relativedelta(day=25, months=1)
                    elif round(dias, 1)==15.2:
                        date_start += relativedelta(day=25) if date_start.day < 15 else relativedelta(day=10, months=1)
                    else:
                        date_start = date_start + timedelta(days=dias)
                    data['date'] = date_start

                data['name'] = '/'
                res = line_obj.create(data)
        elif self.aplicacion=='next':
            data['date'] = date_start #.strftime('%Y-%m-%d')
            data['amount'] = self.monto_total
            res = line_obj.create(data)
        return True

    
    
    def action_confirm(self):
        self.ensure_one()
        if not self.payslip_extra_ids:
            raise UserError(_("Advertencia!\nNo puede confirmar el registro sin Líneas de Descuento"))
        self.payslip_extra_ids.action_confirm()
        self.payslip_extra_ids.action_approve()
        self.write({'state': 'progress'})
        return True
    
    
    def action_cancel(self):
        self.ensure_one()
        if self.state=='draft':
            self.payslip_extra_ids.action_cancel()
        else:
            self.payslip_extra_ids.filtered(lambda x: x.state not in ('cancel', 'rejected', 'done')).action_cancel()
            self.payslip_extra_ids.filtered(lambda x: x.state=='done' and x.payslip_id and x.payslip_id.state=='cancel').action_cancel()
        self.write({'state': 'cancel'})
        return True

    def action_done(self):
        res = self.search([('state','=','progress'), ('saldo','<=',0.001)])
        if res:
            res.write({'state':'done'})
        return True
    
class HRPayslip_Extra_Action(models.TransientModel):
    _name = 'hr.payslip.extra.wizard'
    _description = "Asistente para cambiar el estado de los Extras de Nomina en Batch"
    
    
    
    def action_confirm_extras(self):
        rec_ids = self._context.get('active_ids', [])        
        extra_ids = self.env['hr.payslip.extra'].search([('id','in', rec_ids),('state','=','draft')])
        if not extra_ids:
            raise UserError(_('Advertencia !!!\n\nNingnuo de los registros seleccionados se encuentra en estado Borrador.'))
        return extra_ids.action_confirm()
    
    
    
    def action_approve_extras(self):
        rec_ids = self._context.get('active_ids', [])        
        extra_ids = self.env['hr.payslip.extra'].search([('id','in', rec_ids),('state','=','confirmed')])
        if not extra_ids:
            raise UserError(_('Advertencia !!!\n\nNingnuo de los registros seleccionados se encuentra en estado Confirmado.'))
        return extra_ids.action_approve()


    
    def action_reject_extras(self):
        rec_ids = self._context.get('active_ids', [])        
        extra_ids = self.env['hr.payslip.extra'].search([('id','in', rec_ids),('state','in',('confirmed','approved'))])
        if not extra_ids:
            raise UserError(_('Advertencia !!!\n\nNingnuo de los registros seleccionados se encuentra en estado Confirmado o Aprobado.'))
        return extra_ids.action_reject()
    
    
    
    
    def action_cancel_extras(self):
        rec_ids = self._context.get('active_ids', [])        
        extra_ids = self.env['hr.payslip.extra'].search([('id','in', rec_ids),('state','in',('draft','confirmed','approved')),('payslip_id','=',False)])
        if not extra_ids:
            raise UserError(_('Advertencia !!!\n\nNingnuo de los registros seleccionados se puede Cancelar porque no se encuentra en estados Borrador / Confirmado / Aprobado.'))
        return extra_ids.action_cancel()
    
    

class HRPayslip_Extra(models.Model):
    _name = 'hr.payslip.extra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Conceptos Extras para Nómina'
    _order = 'date, name'
    
    @api.depends('payslip_input_ids')
    def _get_payroll_input_id_from_payslip(self):
        for rec in self:
            rec.payslip_input_id = rec.payslip_input_ids and rec.payslip_input_ids[0].id or False
    
    
    name    = fields.Char(string="Referencia", required=True, readonly=True, index=True, default='/')
    
    date    = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, index=True, 
                          readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    
    state   = fields.Selection([('draft','Borrador'),
                                ('confirmed', 'Confirmado'),
                                ('approved', 'Aprobado'),
                                ('done', 'En Nómina'),
                                ('cancel', 'Cancelado'),
                                ('rejected', 'Rechazado')],
                              string='Estado', default='draft', index=True, tracking=True)
    
    employee_id         = fields.Many2one('hr.employee', string='Empleado', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]}, index=True, tracking=True)
    
    contract_id         = fields.Many2one('hr.contract', string='Contrato', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]})
    
    department_id       = fields.Many2one('hr.department', related="contract_id.department_id", 
                                          readonly=True, store=True)
    
    hr_salary_rule_id   = fields.Many2one('hr.salary.rule', string='Concepto', required=True, readonly=True,
                                          states={'draft': [('readonly', False)]}, index=True, 
                                          domain=[('can_be_payroll_extra','=',True)],
                                          tracking=True)
    tipopercepcion_id   = fields.Many2one('sat.nomina.tipopercepcion', related="hr_salary_rule_id.tipopercepcion_id", 
                                          readonly=True, store=False)
    tipopercepcion_code = fields.Char(string="Código Tipo Percepción", related="tipopercepcion_id.code", 
                                      readonly=True, store=False)
    
    sat_nomina_tipohoraextra_id  = fields.Many2one('sat.nomina.tipohoraextra', string="Tipo Hora Extra",
                                                  readonly=True, states={'draft': [('readonly', False)]})
    qty                 = fields.Float(string='Cantidad', default=1, required=True, readonly=True,
                                       digits=(16,4),
                                       states={'draft': [('readonly', False)]}, 
                                       tracking=True)
    
    amount              = fields.Float(string='Monto', digits=(18,2), default=0, required=True, readonly=True,
                                          states={'draft': [('readonly', False)]}, tracking=True)
    
    payslip_id          = fields.Many2one('hr.payslip', related="payslip_input_id.payslip_id",
                                          string='Nómina', readonly=True, store=True)
    payslip_state       = fields.Selection(readonly=True, related='payslip_id.state',
                                          string="Estado Nómina")
    payslip_input_ids   = fields.One2many('hr.payslip.input', 'payslip_extra_id', 
                                          string="Entradas de Nómina", readonly=True)
    payslip_input_id    = fields.Many2one('hr.payslip.input', string='Entrada de Nómina', 
                                           compute='_get_payroll_input_id_from_payslip', readonly=True, store=True)
    
    payslip_date        = fields.Date(string='Fecha Nómina', related='payslip_id.date_to', 
                                      readonly=True, store=True)
    
    company_id          = fields.Many2one('res.company', 'Compañía', default=lambda self: self.env.company)
    
    extra_discount_id   = fields.Many2one('hr.payslip.extra.discounts', string='Descuento programado')

    leave_id = fields.Many2one('hr.leave', string="Ausencia", readonly=True)
    leave_allocation_id = fields.Many2one('hr.leave.allocation', string="Ausencia Disponible", readonly=True)
    
    notes             = fields.Text(string="Observaciones")
    
    settlement_id = fields.Many2one('hr.settlement', string="Finiquito / Liquidación",
                                   index=True)
    
    _sql_constraints = [
        ('name_company_unique', 'unique(name,company_id)','La Referencia del registro debe ser única'),
        ('check_amount_and_qty', 'CHECK(amount > 0 and qty > 0)',
         'El monto y/o cantidad debe ser mayor a cero.')
    ]
    
    
    @api.onchange('employee_id', 'date')
    def onchange_employee(self):
        if self.employee_id and self.date:
            contract_ids = self.employee_id._get_contracts(self.date, self.date, states=['open','close'])
            _logger.info("contract_ids: %s" % contract_ids)
            contract = contract_ids and contract_ids[0] or False
            self.contract_id = contract and contract.id or False
            self.amount = contract and contract.cfdi_sueldo_base or 1
        else:
            self.contract_id = False
            
    
    
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('hr.payslip.extra') or '/'
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.payslip.extra') or '/'
        return super(HRPayslip_Extra, self).create(vals)

    
    
    def write(self, values):
        if 'payslip_input_id' in values:
            if values['payslip_input_id']:
                values.update({'state':'done'})
            else:
                values.update({'state':'approved'})
        return super(HRPayslip_Extra, self).write(values)
    
    
    
    def action_confirm(self):
        self.write({'state' : 'confirmed'})
        return True
    
    
    
    def action_reject(self):
        recs = self.filtered(lambda x: x.state in ('draft','confirmed','approved') and (not x.payslip_id or (x.payslip_id and x.payslip_state !='cancel')))
        recs.write({'state' : 'rejected', 'leave_id' : False})
        return True
    
    
    
    def action_cancel(self):
        for rec in self:
            if rec.payslip_id and rec.payslip_id.state!='cancel':
                raise UserError(_("Advertencia !!!\n\nNo se puede cancelar porque el Extra de Nómina %s ya se encuentra enlazado a una Nómina.") % rec.name)
        self.write({'state' : 'cancel'})
        return True
    
    
    def action_approve(self):
        self.write({'state' : 'approved'})
        return True
    
