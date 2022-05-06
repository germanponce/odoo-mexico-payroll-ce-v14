# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY
from datetime import datetime, timedelta, date, time
import math
import logging
_logger = logging.getLogger(__name__)

class HRLeaves(models.Model):
    _inherit = 'hr.leave'
    
    incapacidad_folio = fields.Char(string="Folio Incapacidad", readonly=True,
                                    states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    incapacidad_control = fields.Selection([('0', 'Ninguna'),
                                            ('1', 'Unica'),
                                            ('2', 'Inicial'),
                                            ('3', 'Subsecuente'),
                                            ('4', 'Alta médica o ST-2'),
                                            ('6', 'Prenatal'),
                                            ('7', 'Enlace'),
                                            ('8', 'Postnatal'),
                                           ],
                                           string="Control Incapacidad", default='0', readonly=True,
                                           states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})

    incapacidad_porcentaje = fields.Integer(string="% Incapacidad", default=0,
                                            help="""Digite, en su caso, el porcentaje de incapacidad anotado en el Dictamen de Incapacidad Permanente o de Defunción por Riesgo de Trabajo expedido por el IMSS.""",
                                            readonly=True,
                                            states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    incapacidad_secuela = fields.Selection([('0', 'Ninguna'),
                                            ('1', 'Incapacidad Temporal'),
                                            ('2', 'Valuación Inicial Provisional'),
                                            ('3', 'Valuación Inicial Definitiva'),
                                            ('4', 'Defunción'),
                                            ('5', 'Recaída'),
                                            ('6', 'Valuación posterior a la fecha de alta'),
                                            ('7', 'Revaluación provisional'),
                                            ('8', 'Recaída sin alta médica (No Usar)'),
                                            ('9', 'Revaluación definitiva')
                                           ],
                                           string="Secuela o Consecuencia", default='0', readonly=True,
                                           states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    incapacidad_tipo_riesgo = fields.Selection([('0', 'No aplica'),
                                                ('1', 'Accidente de Trabajo'),
                                                ('2', 'Accidente de Trayecto'),
                                                ('3', 'Enfermedad Profesional')],
                                               string='Tipo Riesgo', readonly=True,
                                               states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    
    
    @api.constrains('es_incapacidad', 'state','incapacidad_folio','incapacidad_porcentaje')
    def _check_incapacidad(self):
        for rec in self.filtered(lambda x: x.es_incapacidad and x.state in ('draft','validate','confirm')):
            _logger.info("rec.incapacidad_folio")
            if len(rec.incapacidad_folio)!=8:
                raise ValidationError(_('Error, el Folio de Incapacidad %s no tiene longitud de 8 caracteres') % rec.incapacidad_folio)
            if rec.incapacidad_porcentaje < 0 or rec.incapacidad_porcentaje > 100:
                raise ValidationError(_('Error, el Porcentaje Incapacidad debe ser entre 0 y 100') % rec.incapacidad_porcentaje)    
            
        return True
    
    
    
class hr_leave_crea_incapacity_imss(models.TransientModel):
    _name = 'hr.leave.imss.incapacity.wizard'
    _description = "Asistente para crear Incapacidad del IMSS"
    
    
    hr_leave_ids = fields.Many2many('hr.leave', string="Ausencias",
                                   domain="[('es_incapacidad','=',True),('state','=','validate')]")
    date = fields.Date(string="Fecha Incapacidad", required=True,
                       default=fields.Date.context_today)
    
    
    @api.model
    def default_get(self, default_fields):
        res = super(hr_leave_crea_incapacity_imss, self).default_get(default_fields)
        record_ids =  self._context.get('active_ids',[])
        imss_line_obj = self.env['hr.employee.imss.incapacity.line']
        for leave in self.env['hr.leave'].browse(record_ids):
            resx = imss_line_obj.search([('leave_id','=',leave.id)])
            if resx:
                raise ValidationError(_('Advertencia!\n\nLa Ausencia para %s ya se encuentra en un registro de Incapacidad de IMSS, no puede duplicar el registro') % leave.employee_id.name)
            if leave.state != 'validate':
                raise ValidationError(_('Advertencia!\n\nLa Ausencia para %s no se encuentra en estado Aprobado. Solo registros en este estado se pueden agregar a la Incapacidad del IMSS') % leave.employee_id.name)
        
        res.update({'hr_leave_ids'  : record_ids,
                   })
        return res
        
        
    def crear_imss_incapacity(self):
        if not self.hr_leave_ids:
            raise UserError(_("Advertencia !\n\nNo hay ninguna Ausencia a usar para crear las Incapacidades del IMSS."))
        
        
        line_ids = []
        for l in self.hr_leave_ids:
            line_ids.append((0,0,{'leave_id' : l.id}))
        data = {'date'  : self.date,
                'line_ids' : line_ids}
                #'contract_ids' : [(6,0, [rec.contract_id.id for rec in self.hr_leave_ids])]}
        
        if any(rec.state!='validate' for rec in self.hr_leave_ids):
            raise ValidationError(_('Advertencia!\n\nNo puede incluir Ausencias que no estén en estado Aprobado'))
        incapacity_obj = self.env['hr.employee.imss.incapacity']
        incapacity = incapacity_obj.new(data)
        #incapacity._onchange_contract_ids()
        incapacity_data = incapacity._convert_to_write(incapacity._cache)
        incapacity_id = incapacity_obj.create(incapacity_data)
        
        
        action = self.env.ref('l10n_mx_payroll_imss.action_hr_employee_imss_incapacity').read()[0]
        form_view = [(self.env.ref('l10n_mx_payroll_imss.hr_employee_imss_incapacity_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
        else:
            action['views'] = form_view
        action['res_id'] = incapacity_id.id
        return action    