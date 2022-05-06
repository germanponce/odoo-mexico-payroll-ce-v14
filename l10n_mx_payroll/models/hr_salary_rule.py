# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
import logging
_logger = logging.getLogger(__name__)

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    company_id = fields.Many2one('res.company', string='Company', required=False,
        copy=False, default=lambda self: self.env.company)

    rule_ids = fields.Many2many('hr.salary.rule', string='Salary Rules')
    
    # Se repite para hacerlo compatible con la version CE
    journal_id = fields.Many2one('account.journal', 'Salary Journal', readonly=False, required=False,
        company_dependent=True,
        default=lambda self: self.env['account.journal'].search([
            ('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1))
    
    
class HRSalaryRule(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin','hr.salary.rule']
    _name = 'hr.salary.rule'
    _description = "Regla Salarial con Mail Mixin"
    _order = 'sequence, code, name, id'
    
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
    
    
    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    can_be_payroll_extra = fields.Boolean(string="Concepto para Extras de Nómina",
                                          help="Si está activo entonces puede usar el concepto para Extras de Nómina", 
                                          default=False, index=True, tracking=True)
    tipo_gravable = fields.Selection([('gravable' , 'Gravado'),
                                      ('exento'   , 'Exento')],
                                     string="Grava",
                                     required=True, default='gravable', tracking=True)
    
    nomina_aplicacion       = fields.Selection([('percepcion','Percepción'),
                                                ('deduccion', 'Deducción'),
                                                ('otrospagos', 'Otros Pagos'),
                                                ('incapacidad', 'Incapacidad'),
                                                ('no_aplica', 'No Aplica')],
                                               string="Uso en Nómina", required=True, default='no_aplica', tracking=True)
    tipopercepcion_id   = fields.Many2one('sat.nomina.tipopercepcion', string="·Tipo Percepción", tracking=True)
    tipodeduccion_id    = fields.Many2one('sat.nomina.tipodeduccion', string="·Tipo Deducción", tracking=True)
    tipootropago_id     = fields.Many2one('sat.nomina.tipootropago', string="·Tipo Otro Pago", tracking=True)
    tipoincapacidad_id  = fields.Many2one('sat.nomina.tipoincapacidad', string="·Tipo Incapacidad", tracking=True)
    no_suma             = fields.Boolean(string="No suma", index=True,
                                         default=lambda x: False, tracking=True,
                                         help="Active este check si el concepto es pagado en especie o bien, el monto no afecta con lo efectivamente pagado o es requerido para aparecer en el XML de Nómina "
                                              "Por ejemplo: \n\nPercepciones:\n   - Vales de Despensa\n   - Vales de Combustible, etc.\n\nOtros Pagos:\n   - Subsidio al Empleo Causado")
    es_subsidio_causado = fields.Boolean(string="Es Subsidio Causado",
                                         default=lambda x: False, tracking=True,
                                         help="Active este check si el concepto es el Subsidio Causado requerido para ser insertado en el XML")

    otro_clasificador = fields.Selection([('fondo_ahorro_empresa','Fondo de Ahorro aportado por Empresa'),
                                          ('fondo_ahorro_empleado','Fondo de Ahorro aportado por el Empleado'),
                                          ('na','No Aplica'),
                                         ], string="Otro Clasificador",
                                         default='na', tracking=True,
                                         help="Este Clasificador es para diferenciar algunos conceptos con Clave Común en el SAT, por ejemplo: Fondo de Ahorro, Descuentos, etc")
    struct_id = fields.Many2one('hr.payroll.structure', string="Salary Structure", required=False)
    
    @api.constrains('code')
    def _check_for_code_length_3_or_more(self):
        for rec in self.filtered(lambda x: x.appears_on_payslip and x.nomina_aplicacion!='no_aplica'):
            if len(rec.code) < 3:
                raise UserError(_('El Código para Reglas Salariales que aparecen en Nómina debe contener mínimo 3 caracteres: %s - %s') % (rec.code, rec.name))
        return True
    
    
    
    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """        
        self.ensure_one()
        localdict.update({'datetime' : datetime,
                          'date'     : date,
                          'timedelta': timedelta,
                          'relativedelta': relativedelta,
                          '_logger'  : _logger,
                          'sorted'   : sorted,
                          'eval'     : eval,
                          'env'      : self.env})
        if self.amount_select == 'fix':
            try:
                return self.amount_fix or 0.0, float(safe_eval(self.quantity, localdict)), 100.0
            except Exception as e:
                raise UserError(_('Wrong quantity defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))
        if self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage or 0.0)
            except Exception as e:
                raise UserError(_('Wrong percentage base or quantity defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))
        else:  # python code
            #try:
            safe_eval(self.amount_python_compute or 0.0, localdict, mode='exec', nocopy=True)
            return float(localdict['result']), localdict.get('result_qty', 1.0), localdict.get('result_rate', 100.0)
            #except Exception as e:
            #    raise UserError(_('Wrong python code defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))
    


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'
    
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
