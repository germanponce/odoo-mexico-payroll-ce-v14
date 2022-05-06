# -*- coding: utf-8 -*-
from odoo import api, models, fields, tools, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import logging
_logger = logging.getLogger(__name__)

class HRPayslipCancelSAT(models.TransientModel):
    _name = 'hr.payslip.cfdi.cancel.sat'
    _description = 'Wizard para solicitar la Cancelacion del CFDI de Nómina de acuerdo a nuevo esquema de cancelacion del SAT'
    
    payslip_ids = fields.Many2many('hr.payslip', 'hr_payslip_cfdi_cancel_rel', 'wizard_id', 'slip_id',
                                   string="Recibos de Nómina a Cancelar")
    
    payslip_run_id = fields.Many2one('hr.payslip.run', required=False, string="Lista de Nómina a Cancelar")

    
    cfdi_motivo_cancelacion = fields.Selection([
        #('01', '[01] Comprobantes emitidos con errores con relación'),
        ('02', '[02] Comprobantes emitidos con errores sin relación'),
        ('03', '[03] No se llevó a cabo la operación'),
        #('04', '[04] Operación nominativa relacionada en una factura global')
    ], required=True, default='03', string="Motivo Cancelación")
    
    #uuid_relacionado_cancelacion = fields.Char(string="UUID Relacionado en Cancelación")
    
    
    @api.model
    def default_get(self, default_fields):
        res = super(HRPayslipCancelSAT, self).default_get(default_fields)
        if self._context.get('active_model') == 'hr.payslip':
            res.update({'payslip_ids' : [(6,0,self._context.get('active_ids', []))]})
        elif self._context.get('active_model') == 'hr.payslip.run':
            res.update({'payslip_run_id' : self._context.get('active_ids', []) and self._context.get('active_ids', [])[0] or False})
        else:
            raise ValidationError(_('Advertencia ! Error de programación, revise con el equipo técnico'))
                        
        return res
        
        
    def request_cancel(self):
        if self.payslip_ids:
            self.payslip_ids.write({'cfdi_motivo_cancelacion' : self.cfdi_motivo_cancelacion,
                                #'uuid_relacionado_cancelacion' : self.uuid_relacionado_cancelacion,
                               })
            self.payslip_ids.action_cancel()
        elif self.payslip_run_id:
            self.payslip_run_id.slip_ids.write({'cfdi_motivo_cancelacion' : self.cfdi_motivo_cancelacion,
                                                #'uuid_relacionado_cancelacion' : self.uuid_relacionado_cancelacion,
                                               })
            self.payslip_run_id.to_cancel=True
            self.payslip_run_id.action_cancel_close()
        return True