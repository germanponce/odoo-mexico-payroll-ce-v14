# -*- encoding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression
from datetime import timedelta, date, datetime
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)


meses = ['dummy','Enero','Febrero','Marzo','Abril','Mayo', 'Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

###### HRPayrollPeriod #########    
class HRPayrollPeriod(models.Model):
    _name = "hr.payroll.period"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Periodos de Nominas'
    _order = 'anio,code'
    
    
    name = fields.Text(string="Descripción", required=True, index=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    code = fields.Char(string="Prefijo", size=12, required=True, index=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    anio = fields.Integer(string="Año", required=True, tracking=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    dias_para_pago = fields.Integer(string="Días para pago", required=True,
                                    help="Días después del final del periodo de Nómina para poner Fecha de pago",
                                    default=2, tracking=True,
                                    readonly=True, states={'draft': [('readonly', False)]})
    period_type = fields.Selection([('semanal','Semanal'),
                                    ('quincenal','Quincenal'),
                                    ('decenal','Decenal'),
                                    ('mensual','Mensual'),
                                   ], string="Tipo Periodo", default="semanal", required=True,
                                   tracking=True,
                                   readonly=True, states={'draft': [('readonly', False)]})
    state       = fields.Selection([('draft','Borrador'),
                                    ('confirm', 'Confirmado'),
                                    ('cancel','Cancelado')],
                                  string="Estado", default='draft')
    
    struct_id = fields.Many2one('hr.payroll.structure', string="Estructura Salarial", required=True, tracking=True,
                                readonly=True, states={'draft': [('readonly', False)]})
    journal_id = fields.Many2one('account.journal', string="Diario Contable", required=True,
                                 domain="[('type','=','general')]", tracking=True,
                                 readonly=True, states={'draft': [('readonly', False)]})
    date_from = fields.Date(string="Desde", required=True, tracking=True,
                            readonly=True, states={'draft': [('readonly', False)]})
    date_to    = fields.Date(string="Hasta", required=True, tracking=True,
                             readonly=True, states={'draft': [('readonly', False)]})
    line_ids = fields.One2many('hr.payroll.period.line','period_id', string="Líneas", 
                               readonly=True, states={'draft': [('readonly', False)]})
    
    company_id          = fields.Many2one('res.company', 'Compañía', 
                                          default=lambda self: self.env.company)
    notes = fields.Text(string="Observaciones", readonly=True, states={'draft': [('readonly', False)]})
    
    _sql_constraints = [
        ('code_unique', 'unique(anio,period_type,state)', 'El Tipo de Periodo + Prefijo + Año deben ser único')]
    
    
    @api.depends('name', 'code', 'anio')
    def name_get(self):
        result = []
        for rec in self:
            name = "[" + str(rec.anio) + ' - ' + rec.code + "] " + rec.name
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
        rec_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return models.lazy_name_get(self.browse(rec_ids).with_user(name_get_uid))
    
    
    def get_period_name(self, date_from, date_to):
        if date_from.year != date_to.year:
            period_name =  "Periodo del %s de %s de %s al %s de %s de %s" % (int(date_from.strftime('%d')), meses[int(date_from.strftime("%m"))], date_from.strftime("%Y"), int(date_to.strftime('%d')), meses[int(date_to.strftime("%m"))], date_to.strftime("%Y"))
        elif date_from.month != date_to.month:
            period_name = "Periodo del %s de %s al %s de %s de %s" % (int(date_from.strftime('%d')), meses[int(date_from.strftime("%m"))], int(date_to.strftime('%d')), meses[int(date_to.strftime("%m"))], date_from.strftime("%Y"))
        else:
            period_name = "Periodo del %s al %s de %s de %s" % (date_from.strftime('%d'), date_to.strftime('%d'), meses[int(date_from.strftime("%m"))], date_from.strftime("%Y"))
        return period_name
    
    
    def get_default_data_dict(self):
        return {
            'struct_id'     : self.struct_id.id,
            'tiponomina_id' : self.env['sat.nomina.tiponomina'].search([('code','=','O')], limit=1).id,
            'journal_id'    : self.journal_id.id,
        }
    
    def compute_lines(self):
        for line in self.line_ids:
            if line.payslip_run_id.state not in ('draft','cancel'):
                raise ValidationError(_("No es posible recalcular los periodos porque uno de ellos ya tiene movimientos\n:Periodo: %s") % line.payslip_run_id.name)
            if line.payslip_run_id.slip_ids:
                raise ValidationError(_("No es posible recalcular los periodos porque uno de ellos ya tiene movimientos\n:Periodo: %s") % line.payslip_run_id.name)
            line.payslip_run_id.unlink()
        self.line_ids.unlink()
        
        payslip_run_obj = self.env['hr.payslip.run']
        period_line_obj = self.env['hr.payroll.period.line']
        struct_id = self.struct_id.id
        tiponomina_id = self.env['sat.nomina.tiponomina'].search([('code','=','O')], limit=1).id
        dias_para_pago = self.dias_para_pago
        journal_id = self.journal_id.id
        if self.period_type in ('semanal','decenal'):
            dias = 6 if self.period_type=='semanal' else 9
            date_from = self.date_from
            flag = True
            cont = 0
            while flag:
                date_to = date_from + timedelta(days=dias)
                cont += 1
                name = '%s %s %s: %s' % (str(self.anio), self.code, str(cont), self.get_period_name(date_from, date_to))
                data = self.get_default_data_dict()
                data.update({
                        'name'      : name,
                        'date_start': date_from,
                        'date_end'  : date_to,
                        'date_payroll' : date_to + timedelta(days=dias_para_pago),
                        'date_account' : date_to + timedelta(days=dias_para_pago),
                        
                       })
                xres = payslip_run_obj.create(data)
                
                data2 = {'period_id' : self.id,
                         'payslip_run_id' : xres.id,
                         'name' : name,
                         'anio' : self.anio,
                         'period_type' : self.period_type,
                        }
                
                xres = period_line_obj.create(data2)
                
                date_from = date_to + timedelta(days=1)
                if date_from > self.date_to:
                    flag = False
        elif self.period_type=='quincenal':
            cont = 0
            for mes in range(12):
                primera = True
                for quincena in [1,2]:
                    cont += 1
                    if primera:
                        date_from = self.date_from + relativedelta(months=mes)
                        date_to = self.date_from + relativedelta(months=mes,day=15)
                        primera=False
                    else:
                        date_from = self.date_from + relativedelta(months=mes,day=16)
                        date_to = self.date_from + relativedelta(months=mes+1,days=-1)
                        primera=True
                    name = '%s %s: %s' % (self.code, str(cont), self.get_period_name(date_from, date_to))
                    data = {'struct_id' : struct_id,
                            'name'      : name,
                            'date_start': date_from,
                            'date_end'  : date_to,
                            'tiponomina_id' : tiponomina_id,
                            'date_payroll' : date_to + timedelta(days=dias_para_pago),
                            'date_account' : date_to + timedelta(days=dias_para_pago),
                            'journal_id' : journal_id,
                           }
                    xres = payslip_run_obj.create(data)

                    data2 = {'period_id' : self.id,
                             'payslip_run_id' : xres.id,
                             'name' : name,
                             'anio' : self.anio,
                             'period_type' : self.period_type,
                            }

                    xres = period_line_obj.create(data2)
                    
        elif self.period_type=='mensual':
            cont = 0
            for mes in range(12):
                cont += 1
                date_from = self.date_from + relativedelta(months=mes)
                date_to = self.date_from + relativedelta(months=mes+1,days=-1)
                        
                name = '%s %s: %s' % (self.code, str(cont), self.get_period_name(date_from, date_to))
                data = {'struct_id' : struct_id,
                        'name'      : name,
                        'date_start': date_from,
                        'date_end'  : date_to,
                        'tiponomina_id' : tiponomina_id,
                        'date_payroll' : date_to + timedelta(days=dias_para_pago),
                        'date_account' : date_to + timedelta(days=dias_para_pago),
                        'journal_id' : journal_id,
                       }
                xres = payslip_run_obj.create(data)

                data2 = {'period_id' : self.id,
                         'payslip_run_id' : xres.id,
                         'name' : name,
                         'anio' : self.anio,
                         'period_type' : self.period_type,
                        }

                xres = period_line_obj.create(data2)

        return True
            
    
    def action_confirm(self):
        if not self.line_ids:
            raise ValidationError(_("No puede confirmar un registro sin Líneas"))
        self.write({'state':'confirm'})
        return True
        
    def action_cancel(self):
        listas = self.env['hr.payslip.run'].browse([])
        for line in self.line_ids:
            if line.payslip_run_id.state not in ('draft','cancel') or line.payslip_run_id.slip_ids:
                raise ValidationError(_("No es posible Cancelar este registro porque uno de los periodos ya tiene movimientos\n:Periodo: %s") % line.payslip_run_id.name)
            listas += line.payslip_run_id
        self.line_ids.unlink()
        listas.unlink()
        self.write({'state' :'cancel'})
        return True
    
    def set_to_draft(self):
        self.write({'state' :'draft'})
        return True
        
###### HRPayrollPeriodoLine #########    
class HRPayrollPeriodoLine(models.Model):
    _name = "hr.payroll.period.line"
    _description = 'Lineas de Periodos de Nominas'
    _order = 'anio,period_type'
    
    
    period_id = fields.Many2one('hr.payroll.period', string="Periodo", required=True)
    payslip_run_id = fields.Many2one('hr.payslip.run', string="Lista de Nóminas", required=False)
    name = fields.Text(string="Descripción", required=True, index=True)
    anio = fields.Integer(string="Año", required=True)
    period_type = fields.Selection([('semanal','Semanal'),
                                    ('quincenal','Quincenal'),
                                    ('decenal','Decenal'),
                                    ('mensual','Mensual'),
                            ],
                           string="Tipo Periodo")
    date_start = fields.Date(string="Desde", related="payslip_run_id.date_start", readonly=False)
    date_end   = fields.Date(string="Hasta", related="payslip_run_id.date_end", readonly=False)
    date_payroll = fields.Date(string="Fecha Pago", related="payslip_run_id.date_payroll", readonly=False)
