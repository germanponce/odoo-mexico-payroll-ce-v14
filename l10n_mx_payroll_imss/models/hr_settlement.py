# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import time
from dateutil import relativedelta
import logging
_logger = logging.getLogger(__name__)


class hr_settlement(models.Model):
    _inherit="hr.settlement"

    
    causa_baja = fields.Selection([('1', 'Término de Contrato'),
                                   ('2', 'Separación Voluntaria'),
                                   ('3', 'Abandono de Empleo'),
                                   ('4', 'Defunción'),
                                   ('5', 'Clausura'),
                                   ('6', 'Otras'),
                                   ('7', 'Ausentismo'),
                                   ('8', 'Rescisión de Contrato'),
                                   ('9', 'Jubilación'),
                                   ('A', 'Pensión')],
                                  string="Causa de Baja", default='2', index=True,
                                  readonly=True, states={'draft': [('readonly', False)]}, 
                                  tracking=True)
    

class hr_settlement_crea_baja_imss(models.TransientModel):
    _name = 'hr.settlement.baja_imss.wizard'
    _description = "Asistente para crear Bajas del IMSS"
    
    
    hr_settlement_ids = fields.Many2many('hr.settlement', string="Finiquitos")
    date = fields.Date(string="Fecha Baja", required=True,
                      default=fields.Date.context_today)
    
    
    @api.model
    def default_get(self, default_fields):
        res = super(hr_settlement_crea_baja_imss, self).default_get(default_fields)
        record_ids =  self._context.get('active_ids',[])
        imss_line_obj = self.env['hr.employee.imss.line']
        for settlement in self.env['hr.settlement'].browse(record_ids):
            resx = imss_line_obj.search([('contract_id','=',settlement.contract_id.id),
                                        ('state','!=','cancel'),
                                        ('type','=','02')])
            if resx:
                raise ValidationError(_('Advertencia!\n\nEl Finiquito %s ya se encuentra en un registro de Baja de IMSS, no puede duplicar el registro') % settlement.name)
            if settlement.state!='done':
                raise ValidationError(_('Advertencia!\n\nEl Finiquito %s no se encuentra en estado Hecho. Solo registros en este estado se pueden agregar a la Baja del IMSS') % settlement.name)
        
        res.update({'hr_settlement_ids'    : record_ids,
                    'date' : record_ids and settlement.date or fields.Date.context_today
                   })
        return res
        
        
    def crear_baja_imss(self):
        if not self.hr_settlement_ids:
            raise UserError(_("Advertencia !\n\nNo hay ningún Finiquito a usar para crear las Bajas del IMSS."))
        
        
        data = {'date'  : self.date,
                'type'  : '02',
                'contract_ids' : [(6,0, [rec.contract_id.id for rec in self.hr_settlement_ids])]}
        
        if any(rec.state!='done' for rec in self.hr_settlement_ids):
            raise ValidationError(_('Advertencia!\n\nNo puede incluir Finiquitos que no estén en estado Hecho'))
        baja_obj = self.env['hr.employee.imss']
        baja = baja_obj.new(data)
        baja._onchange_contract_ids()
        baja_data = baja._convert_to_write(baja._cache)
        baja_id = baja_obj.create(baja_data)
        
        for l in baja_id.line_ids:
            for rec in self.hr_settlement_ids.filtered(lambda w: w.contract_id.id==l.contract_id.id):
                l.causa_baja = rec.causa_baja
        
        
        action = self.env.ref('l10n_mx_payroll_imss.action_hr_employee_imss_baja').read()[0]
        form_view = [(self.env.ref('l10n_mx_payroll_imss.hr_employee_imss_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
        else:
            action['views'] = form_view
        action['res_id'] = baja_id.id
        return action