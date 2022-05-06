# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

import logging
_logger = logging.getLogger(__name__)


class HRPayslipResendMail(models.TransientModel):
    _name = 'hr.payslip.resend_mail'
    _description = 'Wizard para reenviar el Recibo de Nominas'
    
    slip_ids = fields.Many2many('hr.payslip', 'resend_wiz_id','slip_id','resend_wiz_slip_rel', string="Nóminas")
    
    @api.model
    def default_get(self, fields):
        res = super(HRPayslipResendMail, self).default_get(fields)
        
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')
        if not active_ids or active_model != 'hr.payslip':
            return res
        slips = self.env['hr.payslip'].browse(active_ids)
        if 'l10n_mx_edi_pac_status' in slips[0]._fields:
            slips = self.env['hr.payslip'].browse(active_ids).filtered(lambda w: w.state=='done' and w.l10n_mx_edi_pac_status in ('signed'))
        elif 'cfdi_state' in slips[0]._fields:
            slips = self.env['hr.payslip'].browse(active_ids).filtered(lambda w: w.state=='done' and w.cfdi_state in ('xml_signed', 'pdf','sent'))
        else:
            raise ValidationError("No tiene instalada ninguna Localizacion")
            
        res['slip_ids'] = [(6,0,slips.ids)]
        return res
    
    
    def send_mails(self):
        template_id = self.env['mail.template'].search([('model_id.model', '=', 'hr.payslip'),
                                                            #('company_id','=', company_id),
                                                            #('report_template.report_name', '=',report_name)
                                                           ], limit=1)                            
        if not template_id:
            rec.message_post(body=_('Error en Envío de CFDI por Correo electrónico\n\nNo se pudo enviar los archivos por correo porque no tiene configurada la Plantilla de Correo Electrónico'), 
                                 subtype='notification')
        attachment_obj = self.env['ir.attachment']
        for rec in self.slip_ids:
            _logger.info('Intentando enviar XML y PDF al mail del Empleado - Nomina: %s', rec.number)
            msj = ''
            state = ''
            partner_mail = rec.employee_id.address_home_id.email or False
            user_mail = self.env.user.email or False
            company_id = rec.company_id.id
            address_id = rec.employee_id.address_home_id.address_get(['invoice'])['invoice']
            partner_invoice_address = address_id
            fname_payslip = rec.fname_payslip or ''
            
            adjuntos = attachment_obj.search([('res_model', '=', 'hr.payslip'), 
                                              ('res_id', '=', rec.id)])
            q = True
            attachments = []
            for attach in adjuntos:
                if q and attach.name.endswith('.xml'):
                    attachments.append(attach.id)
                    break

            mail_compose_message_pool = self.env['mail.compose.message']            
            
            ctx = dict(
                default_model='hr.payslip',
                default_res_id=rec.id,
                default_use_template=bool(template_id),
                default_template_id=template_id.id,
                default_composition_mode='comment',
            )
            xres = mail_compose_message_pool.with_context(ctx).onchange_template_id(
                template_id=template_id.id, 
                composition_mode=None,
                model='hr.payslip', res_id=rec.id)
            
            try:
                attachments.append(xres['value']['attachment_ids'][0][2][0])
            except:
                mail_attachments = (xres['value']['attachment_ids'])
                for mail_atch in mail_attachments:
                    if mail_atch[0] == 4:
                        # attachments.append(mail_atch[1])
                        attach_br = self.env['ir.attachment'].browse(mail_atch[1])
                        if attach_br.name != fname_payslip+'.pdf':
                            attach_br.write({'name': fname_payslip+'.pdf'})
                        attachments.append(mail_atch[1])
                        
            xres['value'].update({'attachment_ids' : [(6, 0, attachments)]})
            
            message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
            _logger.info('Antes de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
            xx = message.action_send_mail()
            _logger.info('Despues de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
            rec.write({'cfdi_state': 'sent'})
            rec.message_post(body=_("El CFDI fue enviado exitosamente por correo electrónico..."), 
                             subtype='notification')
            rec.cfdi_state == 'sent'
        return True

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    