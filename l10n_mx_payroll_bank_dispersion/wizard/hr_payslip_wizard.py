# -*- coding: utf-8 -*-

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging
_logger = logging.getLogger(__name__)


class hr_payslip_run_bank_dispersion(models.TransientModel):
    _name = 'hr.payslip.run.bank_dispersion'
    _description = 'Wizard para crear Archivo TXT de Dispersion de Nómina en Portal de Bancos'
    
    bank_id         = fields.Many2one('res.bank', string="Banco", required=True,
                                      domain=[('payroll_batch_file_id','!=',False)])
    payslip_run_id  = fields.Many2one('hr.payslip.run', required=True)
    filename        = fields.Char(string='Nombre de Archivo', size=128)
    txt_file        = fields.Binary(string='Archivo TXT')
    ok              = fields.Boolean("OK")

    @api.model
    def default_get(self, fields):
        rec = super(hr_payslip_run_bank_dispersion, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        # Check for selected hr.payslip.run
        if not active_ids or active_model != 'hr.payslip.run':
            return rec

        bancos = self.env['res.bank'].search([('payroll_batch_file_id','!=',False)])
        
        lista = self.env['hr.payslip.run'].browse(active_ids)
        rec.update({
            'payslip_run_id': lista[0].id,
            'bank_id'       : bancos and bancos[0].id or False,
        })
        return rec
        
    
    def button_get_file(self):
        if not self.bank_id.payroll_batch_file_id:
            raise UserError(_('Error !!!\n\nNo tiene definida la configuración para la generación del archivo de carga batch para el banco.'))
        values = {'o'   : self.payslip_run_id,
                  'bank': self.bank_id}
        res = self.bank_id.payroll_batch_file_id._render(values=values)
        
        filename = self.bank_id.get_payroll_filename(self.payslip_run_id)
        _logger.info("filename: %s" % filename)
        self.write({
            'filename'  : filename,
            'txt_file'  : base64.encodestring(res),
            'ok'        : True,
        })
        return self._reopen_wizard(self.id)
    
    def _reopen_wizard(self, res_id):
        return {'type'      : 'ir.actions.act_window',
                'res_id'    : res_id,
                'view_mode' : 'form',
                'view_type' : 'form',
                'res_model' : 'hr.payslip.run.bank_dispersion',
                'target'    : 'new',
                'name'      : 'Archivo Batch para Dispersión de Nómina'}