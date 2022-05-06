# -*- encoding: utf-8 -*-
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_TIME_FORMAT
from odoo.tools.safe_eval import safe_eval
from datetime import datetime, timedelta, date
from zeep import Client
from zeep.transports import Transport
from itertools import groupby
import time
import pytz
import base64
import xml
import codecs
import traceback
import os
import tempfile
import xmltodict
from lxml import etree
from lxml.objectify import fromstring
#from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit
from suds.plugin import MessagePlugin
from suds.client import Client as Clientx
from suds.client import WebFault
import io
import zipfile
import subprocess

codigo_cancelacion = {
    '201': 'La solicitud de cancelación se registró exitosamente.',
    '202': 'Comprobante cancelado previamente.',
    '211': 'Comprobante enviado a cancelar exitosamente.',
    '205': 'El comprobante aún no se encuentra reportado en el SAT.',
    '402': 'El UUID enviado no tiene un formato correcto.',
    '300': 'Token no es válido',
    '301': 'Token no registrado para esta empresa',
    '302': 'Token ha caducado',
}



class LogPlugin(MessagePlugin):
    def sending(self, context):
        _logger.info(str(context.envelope))
        #print(str(context.envelope))
        return
    def received(self, context):
        _logger.info(str(context.reply))
        #print(str(context.reply))
        return

import logging
_logger = logging.getLogger(__name__)


CFDI_TEMPLATE = 'l10n_mx_payroll.cfdi33_nomina12'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/3.3/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi/data/xslt/3.3/cadenaoriginal_TFD_1_1.xslt'

CFDI_TEMPLATE_40 =         'l10n_mx_payroll_odoo.cfdi40_nomina12'
CFDI_XSLT_CADENA_40 =      'l10n_mx_payroll_odoo/data/xslt/cadenaoriginal_4_0.xslt'
CFDI_XSLT_CADENA_TFD_40 =  'l10n_mx_payroll_odoo/data/xslt/cadenaoriginal_TFD_1_1.xslt'

REPLACEMENTS = [
    ' s. de r.l. de c.v.', ' S. de R.L. de C.V.', ' S. De R.L. de C.V.', ' S. De R.L. De C.V.', ' s. en c. por a.',
    ' S. en C. por A.', ' S. En C. Por A.', ' s.a.b. de c.v.', ' S.A.B. DE C.V.', ' S.A.B. De C.V.', 
    ' S.A.B. de C.V.', ' s de rl de cv', ' S de RL de CV', ' S DE RL DE CV', ' s.a. de c.v.',
    ' S.A. de C.V.', ' S.A. De C.V.', ' S.A. DE C.V.', ' s en c por a', ' S en C por A',
    ' S EN C POR A', ' s. de r.l.', ' S. de R.L.', ' S. De R.L.', ' s. en n.c.',
    ' S. en N.C.', ' S. En N.C.', ' S. EN N.C.', ' sab de cv', ' SAB de CV',
    ' SAB De CV', ' SAB DE CV', ' sa de cv', ' SA de CV', ' SA De CV', 
    ' SA DE CV', ' s. en c.', ' S. en C.', ' S. En C.', ' S. EN C.', 
    ' s de rl', ' S de RL', ' S DE RL', ' s en nc', ' S en NC',
    ' S EN NC', ' s en c', ' S en C', ' S EN C', ' s.c.',
    ' S.C.', ' A.C.', ' a.c.', ' sc', ' SC', ' ac', ' AC',
]

def return_replacement(cadena):
    cad = cadena
    for x in REPLACEMENTS:
        if cad.endswith(x):
            cad = cadena.replace(x, '')
            break
    return cad

CFDI_SAT_QR_STATE = {
    'No Encontrado': 'not_found',
    'Cancelado': 'cancelled',
    'Vigente': 'valid',
}


def create_list_html(array):
    '''Convert an array of string to a html list.
    :param array: A list of strings
    :return: an empty string if not array, an html list otherwise.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'



class HRPayslip(models.Model):
    _inherit = ['hr.payslip', 'mail.thread','l10n_mx_edi.pac.sw.mixin']
    _name="hr.payslip"
    

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('retry', 'Reintentar'),
            ('to_sign', 'Pendiente de Timbrar'),
            ('signed', 'Timbrado'),
            ('to_cancel', 'A Cancelar'),
            ('cancelled', 'Cancelado')
        ],
        string='Estado Timbrado',
        help='Se refiere al Estatus del CFDI dentro del PAC.',
        readonly=True, copy=False, default='to_sign')
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'Estado No definido'),
            ('undefined', 'No Sincronizado Aún'),
            ('not_found', 'No Encontrado'),
            ('cancelled', 'Cancelado'),
            ('valid', 'Válido'),
        ],
        string='Estado en SAT',
        help='Se refiere al Estatus del CFDI dentro del PAC.',
        readonly=True, copy=False, required=True,
        tracking=True, default='undefined')
    l10n_mx_edi_cfdi_amount = fields.Monetary(string='Total', copy=False, readonly=True,
        help='Monto total del CFDI.',
        compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_cfdi_name = fields.Char(string='Nombre Archivo CFDI', copy=False, readonly=True,
        help='El nombre del adjunto del CFDI.')
    l10n_mx_edi_cfdi = fields.Binary(
        string='Contenido CFDI', copy=False, readonly=True,
        help='Contenido del CFDI codificado en base64.'
        ,compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_cfdi_uuid = fields.Char(string='Folio Fiscal (UUID)*', copy=False, readonly=True,
        help='Folio Fiscal del Recibo de Nómina.', store=True, index=True,
        compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_cfdi_certificate_id = fields.Many2one('l10n_mx_edi.certificate',
        string='Certificado Sello Digital', copy=False, readonly=True,
        help='Certificado de Sello Digital usado para la generación del CFDI.',
        compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('RFC PAC', copy=False, readonly=True,
        help='RFC del Proveedor de Timbrado o PAC.',
        compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('RFC Cliente', copy=False, readonly=True,
        help='RFC del Cliente.',
        compute='_compute_cfdi_values', compute_sudo=True)
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origen', copy=False,
        help='En algunos casos la Nómina debe ser cancelada y re-emitirla, para eso es necesario especificar la razón (Clave SAT y el UUID Previo) '
        'Para ello debe ser capturado de la siguiente manera: '
        '\n04|UUID1, UUID2, ...., UUIDn.\n'
        'Ejemplo:\n"04|89966ACC-0F5C-447D-AEF3-3EED22E711EE"')
    
    
    #### ARGIL ARGIL ####
    
    def _get_cfdi_data_dict(self):
        emisor_rfc = self.company_id.partner_id.vat
        emisor_regimen = self.company_id.l10n_mx_edi_fiscal_regime
        
        receptor_rfc = self.employee_id.address_home_id.vat
        
        # Validaciones:
        error = False
        if not self.company_id.registro_patronal:
            error = _("Advertencia !!!\nNo ha definido el Registro Patronal del Emisor, por favor configure ese dato y reintente la operación")
        if not emisor_rfc:
            error = _("Advertencia !!!\nNo ha definido el RFC del Emisor, por favor configure ese dato y reintente la operación")
        if not receptor_rfc:
            error = _("Advertencia !!!\nNo ha definido el RFC del Receptor, por favor configure ese dato y reintente la operación")
        #if not self.employee_id.bank_account_id.acc_number:
        #    error = _("Advertencia !!!\nNo ha definido la cuenta Bancaria del Trabajador, por favor configure ese dato y reintente la operación")
        if not self.employee_id.address_home_id.state_id:
            error = _("Advertencia !!!\nNo ha definido el Estado en la dirección del Trabajador, por favor configure ese dato y reintente la operación")
        if not self.employee_id.num_empleado:
            error = _("Advertencia !!!\nNo ha definido el Número de Empleado del Trabajador, por favor configure ese dato y reintente la operación")
        if self.contract_id.date_start > self.date_to:
            error = _("Advertencia !!!\nLa fecha inicial de Relación Laboral (Contrato => Fecha Inicial) no es menor o igual a la Fecha Final del Periodo de Pago")
            
        contract = self.contract_id
        
        if not (contract.sat_periodicidadpago_id and contract.sat_riesgopuesto_id and \
                contract.sat_tiporegimen_id and contract.sat_tipojornada_id and \
                contract.sindicalizado and contract.sat_tipo_contrato_id):
            raise UserError(_("Advertencia !!!\nFalta información en el Contrato del Trabajador %s, por favor revise y re-intente la operación") % contract.name) 
        
        emisor_rfc = emisor_rfc.replace('&','&amp;')
        if self.company_id.version_de_cfdi_para_nominas=='3.3':
            emisor_nombre = self.company_id.partner_id.name.replace('&','&amp;')
            receptor_nombre = self.employee_id.name
        elif self.company_id.version_de_cfdi_para_nominas=='4.0':
            emisor_nombre = return_replacement(self.company_id.partner_id.name.replace('&','&amp;'))
            if self.employee_id._fields.get('apellido_paterno', False):
                receptor_nombre = '%s%s%s' % (self.employee_id.nombre, ' ' + self.employee_id.apellido_paterno,
                                              self.employee_id.apellido_materno and (' ' + self.employee_id.apellido_materno) or '')
            else:
                receptor_nombre = self.employee_id.name
        receptor_nombre = receptor_nombre.upper().replace('&','&amp;')
        receptor_rfc = receptor_rfc.replace('&','&amp;')

        fecha = str(self.date_payslip_tz).replace(' ','T')
        return {'o'             : self,
                'emisor_rfc'    : emisor_rfc,
                'emisor_nombre' : emisor_nombre.upper(),
                'emisor_regimen': emisor_regimen,
                'receptor_rfc'  : receptor_rfc,
                'receptor_nombre': receptor_nombre,
                'fecha'         : fecha,
                'error'         : error,
               }
    
    
    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        '''Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information contained within the cfdi.
        This can be encoded with the certificate to create the digital seal.
        Since the cadena is generated with the invoice data, any change in it will be noticed resulting in a different
        cadena and so, ensure the invoice has not been modified.

        :param xslt_path: The path to the xslt file.
        :param cfdi_as_tree: The cfdi converted as a tree
        :return: A string computed with the invoice data called the cadena
        '''
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))
    
    def get_xml_to_sign(self):
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._get_cfdi_data_dict()
        
        if 'error' in values and values['error']:
            #self.message_post(body="Error al generar CFDI\n\n" + values['error'],
            #                  )
            return values
        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_username = company_id.l10n_mx_edi_pac_username
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not (pac_username and pac_password):
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

        # -Compute date and time of the invoice
        date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        time_invoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)

        # -----------------------
        # Create the EDI document
        # -----------------------

        # -Compute certificate data
        values['date'] = values['fecha']
        #values['date'] = datetime.combine(
        #    fields.Datetime.from_string(self.payslip_date),
        #    datetime.strptime(time_invoice, '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        if self.company_id.version_de_cfdi_para_nominas=='3.3':
            cfdi = qweb._render(CFDI_TEMPLATE, values=values)
        elif self.company_id.version_de_cfdi_para_nominas=='4.0':
            cfdi = qweb._render(CFDI_TEMPLATE_40, values=values)

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        if self.company_id.version_de_cfdi_para_nominas=='3.3':
            cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA, tree)
        elif self.company_id.version_de_cfdi_para_nominas=='4.0':
            cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA_40, tree)
        # Post append cadena
        tree.attrib['Sello'] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # TODO - Check with XSD
        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}
    
    
    
    def get_cfdi(self):
        attachment_obj = self.env['ir.attachment']
        for rec in self.filtered(lambda w: w.cfdi_timbrar and w.l10n_mx_edi_pac_status in ('retry','to_sign')):
            filename = ('%s-%s-MX-Nomina.xml' % (
                rec.journal_id.code, rec.number.replace('/','_').replace('-','_').replace(' ','_')))
            rec.write({'payslip_datetime' : fields.Datetime.now(),
                       'user_id'          : self.env.user.id,
                      # 'l10n_mx_edi_cfdi_name' : filename
                      })
            
            cfdi_values = rec.get_xml_to_sign()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            try:
                cfdi_xml_obj = etree.fromstring(cfdi)
                _logger.info("·CFDI a enviar al PAC: \n%s" % etree.tostring(cfdi_xml_obj, pretty_print=True).decode())
            except:
                _logger.info("*CFDI a enviar al PAC: \n%s" % cfdi)
            if error:
                # cfdi failed to be generated
                rec.l10n_mx_edi_pac_status = 'retry'
                rec.message_post(body=error)
                continue
            # cfdi has been successfully generated
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            
            attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                'name': filename,
                'res_id': rec.id,
                'res_model': rec._name,
                'datas': base64.encodebytes(cfdi),
                'store_fname': filename,
                'description': _('CFDI Nómina %s') % rec.number,
                'type'        : 'binary',
                })
            rec.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id])
            
            rec.l10n_mx_edi_pac_status = 'to_sign'
            rec.l10n_mx_edi_cfdi_name = filename
            self.env.cr.commit()
            rec._l10n_mx_edi_sign()
            self.env.cr.commit()
            if not rec.l10n_mx_edi_cfdi_uuid:
                continue
            # Argil
            _logger.info('Intentando enviar XML y PDF al mail del Empleado - Nomina: %s', rec.number)
            msj = ''
            state = ''
            partner_mail = rec.employee_id.address_home_id.email or False
            user_mail = self.env.user.email or False
            company_id = rec.company_id.id
            address_id = rec.employee_id.address_home_id.address_get(['invoice'])['invoice']
            partner_invoice_address = address_id
            fname_payslip = rec.fname_payslip or ''
            
            
            """
            if not rec.struct_id or not rec.struct_id.report_id:
                    report = self.env.ref('hr_payroll.action_report_payslip', False)
            else:
                report = rec.struct_id.report_id
            pdf_content, content_type = report.render_qweb_pdf(rec.id)
            if rec.struct_id.report_id.print_report_name:
                pdf_name = safe_eval(rec.struct_id.report_id.print_report_name, {'object': rec})
            else:
                pdf_name = _("Payslip")
            _res = attachment_obj.create({
                'name': pdf_name,
                'type': 'binary',
                'datas': base64.encodebytes(pdf_content),
                'res_model': rec._name,
                'res_id': rec.id
            })
            """
            _logger.info('Creando PDF del Recibo: %s', rec.number)
            
            
            adjuntos = attachment_obj.search([('res_model', '=', 'hr.payslip'), 
                                              ('res_id', '=', rec.id)])
            q = True
            attachments = [] #[_res.id]
            for attach in adjuntos:
                if q and attach.name.endswith('.xml'):
                    attachments.append(attach.id)
                    break
                    
            mail_compose_message_pool = self.env['mail.compose.message']            
            template = self.env['mail.template'].search([('model_id.model', '=', 'hr.payslip'),
                                                           ], limit=1)
            if not template:
                rec.message_post(body=_('Error en Envío de CFDI por Correo electrónico\n\nNo se pudo enviar los archivos por correo porque no tiene configurada la Plantilla de Correo Electrónico'))
                                     
                continue
            ctx = dict(
                default_model='hr.payslip',
                default_res_id=rec.id,
                default_use_template=bool(template),
                default_template_id=template.id,
                default_composition_mode='mass_mail',
            )

            xres = mail_compose_message_pool.with_context(ctx).onchange_template_id(template_id=template.id, composition_mode="comment",model='hr.payslip', res_id=rec.id)
            xres['value'].update({'attachment_ids' : [(6, 0, attachments)]})
            message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
            
            _logger.info('Antes de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
            xx = message.action_send_mail()
            
            _logger.info('Despues de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
            rec.write({'cfdi_state': 'sent'})
            rec.message_post(body=_("El CFDI fue enviado exitosamente por correo electrónico..."))
            
            rec.write({'state': 'done', 'cfdi_state' : 'sent'})

            _logger.info('Fin proceso Timbrado - Recibo de Nómina CFDI: %s', fname_payslip)

       
        return True
            
    
    
    def _l10n_mx_edi_sign(self):
        """Call the sign service with records that can be signed."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'not in', ['signed', 'to_cancel', 'cancelled', 'retry']),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('sign')
    
    
    def _l10n_mx_edi_call_service(self, service_type):
        """Call the right method according to the pac_name, it's info returned
        by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel"""
        invoice_obj = self.env['hr.payslip']
        # Regroup the invoices by company (= by pac)
        comp_x_records = groupby(self, lambda r: r.company_id)
        for company_id, records in comp_x_records:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            # Get the informations about the pac
            pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
            service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
            pac_info = getattr(invoice_obj, pac_info_func)(company_id, service_type)
            # Call the service with invoices one by one or all together according to the 'multi' value.
            # TODO - Check multi
            multi = pac_info.pop('multi', False)
            if multi:
                # rebuild the recordset
                records = self.env['hr.payslip'].search(
                    [('id', 'in', self.ids), ('company_id', '=', company_id.id)])
                getattr(records, service_func)(pac_info)
            else:
                for record in records:
                    getattr(record, service_func)(pac_info)
    
    
    
    def action_cancel(self):
        if not self._context.get('settlement_id', False) and any(x.settlement_id for x in self):
            raise UserError(_("Advertencia !\nNo es posible cancelar una Nómina que fue generada desde un finiquito"))
        if any(not rec.cfdi_motivo_cancelacion for rec in self):
            return {
                'name': _('Solicitar Cancelación'),
                'res_model': 'hr.payslip.cfdi.cancel.sat',
                'view_mode': 'form',
                'context': {
                    'active_model': 'hr.payslip',
                    'active_ids': self.ids,
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
        moves = self.mapped('move_id')
        moves.filtered(lambda x: x.state == 'posted').button_draft()
        moves.filtered(lambda x: x.state == 'draft').button_cancel()
        try:
            moves.unlink()
        except:
            pass
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            record._l10n_mx_edi_cancel()
            record.write({'cfdi_fecha_cancelacion':time.strftime('%Y-%m-%d %H:%M:%S'),})
        x = self.write({'state': 'cancel', 'payslip_run_id' : False})
        return True
    
    
    #### ARGIL ARGIL ####
    
    # -----------------------------------------------------------------------
    # Cancellation
    # -----------------------------------------------------------------------

    
    def cancel(self):
        result = super(HRPayslip, self).cancel()
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            record._l10n_mx_edi_cancel()
        return result

    
    def _l10n_mx_edi_cancel(self):
        """Call the cancel service with records that can be cancelled."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'in', ['to_sign', 'signed', 'to_cancel', 'retry']),
            ('id', 'in', self.ids)])
        for record in records:
            if record.l10n_mx_edi_pac_status in ['to_sign', 'retry']:
                record.l10n_mx_edi_pac_status = 'cancelled'
                record.message_post(body=_('The cancel service has been called with success'))
            else:
                record.l10n_mx_edi_pac_status = 'to_cancel'
        records = self.search([
            ('l10n_mx_edi_pac_status', '=', 'to_cancel'),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('cancel')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        """Retrieve all the cfdi attachments generated for this payslip.

        :return: An ir.attachment recordset
        """
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_name:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', self.l10n_mx_edi_cfdi_name)]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids and attachment_ids[0] or None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        '''Get an objectified tree representing the cfdi.
        If the cfdi is not specified, retrieve it from the attachment.

        :param cfdi: The cfdi as string
        :return: An objectified tree
        '''
        #TODO helper which is not of too much help and should be removed
        self.ensure_one()
        if cfdi is None:
            #cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
            cfdi = self.l10n_mx_edi_cfdi
        return fromstring(cfdi)

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        '''Get the TimbreFiscalDigital node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the TimbreFiscalDigital node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payslip_etree(self, cfdi):
        '''Get the Complement node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the Payment node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        #get the xslt path
        if self.company_id.version_de_cfdi_para_nominas=='3.3':
            xslt_path = CFDI_XSLT_CADENA_TFD
        elif self.company_id.version_de_cfdi_para_nominas=='4.0':
            xslt_path = CFDI_XSLT_CADENA_TFD_40
        #get the cfdi as eTree
        #cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_cfdi
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        return self.l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    
    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        return True


    
    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message)

    
    @api.depends('l10n_mx_edi_cfdi_name', 'l10n_mx_edi_pac_status')
    def _compute_cfdi_values(self):
        for payslip in self:
            attachment_id = payslip.l10n_mx_edi_retrieve_last_attachment()
            if not attachment_id:
                payslip.l10n_mx_edi_cfdi = None
                payslip.l10n_mx_edi_cfdi_supplier_rfc = None
                payslip.l10n_mx_edi_cfdi_customer_rfc = None
                payslip.l10n_mx_edi_cfdi_amount = None
                payslip.l10n_mx_edi_cfdi_certificate_id = None
                payslip.l10n_mx_edi_cfdi_uuid = None
                continue
            # At this moment, the attachment contains the file size in its 'datas' field because
            # to save some memory, the attachment will store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname)
            payslip.l10n_mx_edi_cfdi = datas
            cfdi = datas.replace(
                b'xmlns:schemaLocation', b'xsi:schemaLocation')
            tree = payslip.l10n_mx_edi_get_xml_etree(cfdi)
            # if already signed, extract uuid
            tfd_node = payslip.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                payslip.l10n_mx_edi_cfdi_uuid = tfd_node.get('UUID')
            else:
                cfdi_dict = xmltodict.parse(cfdi)
                try:
                    uuid = cfdi_dict['cfdi:Comprobante']['cfdi:Complemento']['tfd:TimbreFiscalDigital']['@UUID']
                except:
                    uuid = False
                payslip.l10n_mx_edi_cfdi_uuid = uuid
                
            payslip.l10n_mx_edi_cfdi_amount = tree.get('Total', tree.get('total'))
            payslip.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get('Rfc', tree.Emisor.get('rfc'))
            payslip.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get('Rfc', tree.Receptor.get('rfc'))
            certificate = tree.get('noCertificado', tree.get('NoCertificado'))
            payslip.l10n_mx_edi_cfdi_certificate_id = self.env['l10n_mx_edi.certificate'].sudo().search(
                [('serial_number', '=', certificate)], limit=1)

            
    
    def _l10n_mx_edi_create_cfdi_payslip(self):
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()

        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_username = company_id.l10n_mx_edi_pac_username
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not (pac_username and pac_password):
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

        # -Compute date and time of the invoice
        date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        time_invoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)

        # -----------------------
        # Create the EDI document
        # -----------------------

        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.payslip_date),
            datetime.strptime(time_invoice, '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        cfdi = qweb.render(CFDI_TEMPLATE, values=values)

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.env['account.move'].l10n_mx_edi_generate_cadena(
            CFDI_XSLT_CADENA, tree)

        # Post append cadena
        tree.attrib['Sello'] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # TODO - Check with XSD
        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    # Ver si se usa esta o la otra
    
    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return {}
        origin = self.l10n_mx_edi_origin.split('|')
        uuids = origin[1].split(',') if len(origin) > 1 else []
        return {
            'type': origin[0],
            'related': [u.strip() for u in uuids],
            }

    # PENDIENTE
    
    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None):
        '''Post process the results of the cancel service.

        :param cancelled: is the cancel has been done with success
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''

        self.ensure_one()
        if cancelled:
            body_msg = _('The cancel service has been called with success')
            self.l10n_mx_edi_pac_status = 'cancelled'
        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: ') + str(code)])
        if msg:
            post_msg.extend([_('Message: ') + msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg))

    # -------------------------------------------------------------------------
    # SAT/PAC service methods
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_mx_edi_solfact_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        url = 'https://testing.solucionfactible.com/ws/services/Timbrado?wsdl'\
            if test else 'https://solucionfactible.com/ws/services/Timbrado?wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'testing@solucionfactible.com' if test else username,
            'password': 'timbrado.SF.16672' if test else password,
        }

    
    def _l10n_mx_edi_solfact_sign(self, pac_info):
        '''SIGN for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            cfdi = rec.l10n_mx_edi_cfdi
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.timbrar(username, password, cfdi, False)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            res = response.resultados
            msg = getattr(res[0] if res else response, 'mensaje', None)
            code = getattr(res[0] if res else response, 'status', None)
            xml_signed = getattr(res[0] if res else response, 'cfdiTimbrado', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed)
            rec._l10n_mx_edi_post_sign_process(
                xml_signed if xml_signed else None, code, msg)
    
    
    def _l10n_mx_edi_solfact_cancel(self, pac_info):
        '''CANCEL for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            #uuids = [rec.l10n_mx_edi_cfdi_uuid]
            uuids = '%s|%s|' % (rec.l10n_mx_edi_cfdi_uuid, self.cfdi_motivo_cancelacion)
            certificate_ids = rec.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            cer_pem = certificate_id.get_pem_cer(
                certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            key_password = certificate_id.password
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.cancelar(
                    username, password, uuids, cer_pem, key_pem, key_password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            res = response.resultados
            code = getattr(res[0], 'statusUUID', None) if res else getattr(response, 'status', None)
            cancelled = code in ('201', '202', '211')  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            msg = '' if cancelled else getattr(res[0] if res else response, 'mensaje', None)
            code = '' if cancelled else code
            rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)
    
    
    def _l10n_mx_edi_finkok_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        if service_type == 'sign':
            url = 'http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/stamp.wsdl'
        else:
            url = 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'cfdi@vauxoo.com' if test else username,
            'password': 'vAux00__' if test else password,
        }

    def _l10n_mx_edi_finkok_sign(self, pac_info):
        '''SIGN for Finkok.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            #cfdi = base64.decodestring(inv.l10n_mx_edi_cfdi)
            cfdi = rec.l10n_mx_edi_cfdi
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.stamp(cfdi, username, password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = 0
            msg = None
            if response.Incidencias:
                code = getattr(response.Incidencias.Incidencia[0], 'CodigoError', None)
                msg = getattr(response.Incidencias.Incidencia[0], 'MensajeIncidencia', None)
            xml_signed = getattr(response, 'xml', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    def _l10n_mx_edi_finkok_cancel(self, pac_info):
        '''CANCEL for Finkok.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            uuid = rec.l10n_mx_edi_cfdi_uuid
            certificate_ids = rec.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            company_id = self.company_id
            cer_pem = certificate_id.get_pem_cer(
                certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            cancelled = False
            code = False
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                uuid_type = client.get_type('ns0:stringArray')()
                uuid_type.string = [uuid]
                invoices_list = client.get_type('ns1:UUIDS')(uuid_type)
                response = client.service.cancel(
                    invoices_list, username, password, company_id.vat, cer_pem, key_pem)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            if not getattr(response, 'Folios', None):
                code = getattr(response, 'CodEstatus', None)
                msg = _("Cancelling got an error") if code else _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    
    ##### PRODIGIA ######
    
    def _l10n_mx_edi_prodigia_sign(self, pac_info):
        '''SIGN for Prodigia.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        contract = pac_info['contract']
        test = pac_info['test']
        for rec in self:
            cfdi = rec.l10n_mx_edi_cfdi.decode('UTF-8')
            try:
                client = Client(url, timeout=20)
                if(test):
                    response = client.service.timbradoOdooPrueba(
                        contract, username, password, cfdi)
                else:
                    response = client.service.timbradoOdoo(
                        contract, username, password, cfdi)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            msg = getattr(response, 'mensaje', None)
            code = getattr(response, 'codigo', None)
            xml_signed = getattr(response, 'xml', None)
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    
    def _l10n_mx_edi_prodigia_cancel(self, pac_info):
        '''CANCEL Prodigia.
        '''

        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        contract = pac_info['contract']
        test = pac_info['test']
        rfc_receptor = self.employee_id.address_home_id.vat
        if self:
            certificate_id = self[0].company_id.l10n_mx_edi_certificate_ids[0].sudo(
            )
        rfc_emisor = self.company_id
        for rec in self:
            # uuids = [inv.l10n_mx_edi_cfdi_uuid]
            rfc_receptor = rec.employee_id.address_home_id #partner_id
            if rfc_receptor.vat is False:
                raise VaidationError(_("Error !\n\nEl Empleado no tiene RFC definido"))

            uuids = [rec.l10n_mx_edi_cfdi_uuid+"|"+rfc_receptor.vat+
                     "|"+rfc_emisor.vat+"|" + str(rec.sum_percepciones + rec.sum_otrospagos_xml + rec.total_indemnizacion - rec.sum_deducciones)]

            if not certificate_id:
                certificate_id = rec.l10n_mx_edi_cfdi_certificate_id.sudo()
            cer_pem = base64.encodebytes(certificate_id.get_pem_cer(
                certificate_id.content)).decode('UTF-8')
            key_pem = base64.encodebytes(certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)).decode('UTF-8')
            key_password = certificate_id.password
            
            cancelled = False
            if(test):
                cancelled = True
                msg = 'Este comprobante se cancelo en modo pruebas'
                code = '201'
                rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)
                continue
            try:
                client = Client(url, timeout=20)
                response = client.service.cancelar(
                    contract, username, password, rfc_emisor.vat, uuids, cer_pem, key_pem, key_password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = getattr(response, 'codigo', None)
            cancelled = code in ('201', '202')
            msg = '' if cancelled else getattr(response, 'mensaje', None)
            code = '' if cancelled else code
            rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    ##### FIN Prodigia #####
            
    
    ##### SIFEI ######
    
    @api.model
    def _l10n_mx_edi_sifei_info(self, company_id, service_type):
        if company_id.l10n_mx_edi_pac_test_env:
            return {
                'multi': False,  # TODO: implement multi
                'username': company_id.l10n_mx_edi_pac_username,
                'password': company_id.l10n_mx_edi_pac_password,
                'equipo_id' : company_id.l10n_mx_edi_pac_equipo_id,
                'url'       : 'http://devcfdi.sifei.com.mx:8080/SIFEI33/SIFEI?wsdl',
                'cancel_url': 'http://devcfdi.sifei.com.mx:8888/CancelacionSIFEI/Cancelacion?wsdl',
            }
        else:
            return {
                'multi': False,  # TODO: implement multi
                'username': company_id.l10n_mx_edi_pac_username,
                'password': company_id.l10n_mx_edi_pac_password,
                'equipo_id' : company_id.l10n_mx_edi_pac_equipo_id,
                'url': 'https://sat.sifei.com.mx:8443/SIFEI/SIFEI?wsdl',
                'cancel_url': 'https://sat.sifei.com.mx:9000/CancelacionSIFEI/Cancelacion?wsdl',
            }
    
    def _l10n_mx_edi_sifei_sign(self, pac_info):
        '''SIGN for SIFEI.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        equipo_id = pac_info['equipo_id']
        
        for rec in self:
            cfdi = rec.l10n_mx_edi_cfdi #.decode('UTF-8')
            
            ##################
            (fileno, fname_xml) = tempfile.mkstemp(".xml", "odoo_xml_to_sifei__")
            f_argil = open(fname_xml, 'bw')
            f_argil.write(cfdi)
            f_argil.close()
            os.close(fileno)

            xres = os.system("zip -j " + fname_xml.split('.')[0] + ".zip " + fname_xml + " > /dev/null")

            zipped_xml_file = open(fname_xml.split('.')[0] + ".zip", 'rb')
            cfdi_zipped = base64.b64encode(zipped_xml_file.read())
            zipped_xml_file.close()

            client = Clientx(pac_info['url'], plugins=[LogPlugin()])
            
            try:
                resultado = client.service.getCFDI(pac_info['username'], pac_info['password'], cfdi_zipped.decode("utf-8"), ' ', pac_info['equipo_id'])
            except WebFault as f:
                rec.l10n_mx_edi_log_error(_("La llamada al Servicio de Timbrado de SIFEI falló con el siguiente error: <br/>- Código: %s\n<br/>- Error: %s\n<br/>- Mensaje: %s" % (f.fault.detail.SifeiException.codigo, f.fault.detail.SifeiException.error, f.fault.detail.SifeiException.message)))
                continue
                
            fstamped = io.BytesIO(base64.b64decode(str.encode(resultado)))

            zipf = zipfile.ZipFile(fstamped, 'r')
            zipf1 = zipf.open(zipf.namelist()[0])
            cfdi_signed = zipf1.read() #.replace(b'\r',b'').replace(b'\n',b'')
            if cfdi_signed:
                rec._l10n_mx_edi_post_sign_process(base64.encodestring(cfdi_signed), '200', 'OK')
                
                
    def _get_pfx_file_and_password(self):
        certificates = self.company_id.l10n_mx_edi_certificate_ids
        certificate = certificates.sudo().get_valid_certificate()
        certificate_pfx = certificate.pfx.decode("utf-8")
        password =  certificate.password #password.decode("utf-8") 
        return certificate_pfx, password
            

    
    def _l10n_mx_edi_sifei_cancel(self, pac_info):
        '''CANCEL SIFEI.'''

        certificate_pfx, cert_password = self._get_pfx_file_and_password()
        ##################################
        client = Clientx(pac_info['cancel_url'], plugins=[LogPlugin()])
        
        try:
            params = '|%s|%s||' % (self.l10n_mx_edi_cfdi_uuid, self.cfdi_motivo_cancelacion)
            resultado = client.service.cancelaCFDI(pac_info['username'], 
                                                   pac_info['password'], 
                                                   self.company_id.vat,
                                                   certificate_pfx, 
                                                   cert_password, 
                                                   params)
                                                   #move.l10n_mx_edi_cfdi_uuid)
            
            
            try:
                res = xmltodict.parse(resultado)
                msg = _('Se solicitó la Cancelación del CFDI con Folio: %s<br/>'
                        'Fecha: %s<br/>'
                        'Código de Cancelación: %s - %s<br/>'
                        'Sello SAT: %s'
                       )  % (res['Acuse']['Folios']['UUID'],
                             res['Acuse']['@Fecha'],
                             res['Acuse']['Folios']['EstatusUUID'],
                             res['Acuse']['Folios']['EstatusUUID'] in codigo_cancelacion and codigo_cancelacion[res['Acuse']['Folios']['EstatusUUID']] or 'Sin descripción',
                             res['Acuse']['Signature']['SignedInfo']['Reference']['DigestValue'],
                               )
                self.message_post(body=msg)
                    
            except:
                pass
            
        except WebFault as f:
            self.l10n_mx_edi_log_error(_("La llamada al Servicio de Cancelación de SIFEI falló con el siguiente error: <br/>- Código: %s\n<br/>- Error: %s\n<br/>- Mensaje: %s" % (f.fault.detail.SifeiException.codigo, f.fault.detail.SifeiException.error, f.fault.detail.SifeiException.message)))
            
        code = '201'
        cancelled = code in ('201', '202')
        msg = '' # if cancelled else getattr(res, 'mensaje', None)
        #code = '' if cancelled else code
        self._l10n_mx_edi_post_cancel_process(True, code, msg)
        return

    ##### FIN SIFEI #####
    
    
    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        """Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :param code: an eventual error code
        :param msg: an eventual error msg
        """
        # TODO - Duplicated
        self.ensure_one()
        if xml_signed:
            if type(xml_signed) is not bytes:                
                xml_signed = str.encode(xml_signed)
            try:
                if type(xml_signed) is bytes:
                    cfdi_xml_obj = etree.fromstring(xml_signed)
                else:
                    cfdi_xml_obj = etree.fromstring(base64.decodebytes(xml_signed))
                _logger.info("·CFDI Timbrado: \n%s" % etree.tostring(cfdi_xml_obj, pretty_print=True).decode())
            except:
                _logger.info("CFDI Timbrado: \n%s" % base64.decodebytes(xml_signed))
            
            body_msg = _('The sign service has been called with success')
            # Update the pac status
            self.l10n_mx_edi_pac_status = 'signed'
            self.l10n_mx_edi_cfdi = xml_signed
            # Update the content of the attachment
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            attachment_id.write({
                'datas': xml_signed,
                'mimetype': 'application/xml'
            })
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: ') + str(code)])
        if msg:
            post_msg.extend([_('Message: ') + msg])
        #_logger.info("Estado Timbrado: %s" % post_msg)
        self.message_post(
            body=body_msg + create_list_html(post_msg))

    
    def l10n_mx_edi_update_pac_status(self):
        """Synchronize both systems: Odoo & PAC if the invoices need to be
        signed or cancelled."""
        # TODO - Duplicated
        for record in self:
            if record.l10n_mx_edi_pac_status == 'to_sign':
                record._l10n_mx_edi_sign()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()
            elif record.l10n_mx_edi_pac_status == 'retry':
                record._l10n_mx_edi_retry()

    
    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the invoice is valid.
        """
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        for rec in self.filtered(lambda r: r.l10n_mx_edi_is_required() and
                                 r.l10n_mx_edi_pac_status in ['signed', 'cancelled']):
            supplier_rfc = rec.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = rec.l10n_mx_edi_cfdi_customer_rfc
            total = 0
            uuid = rec.l10n_mx_edi_cfdi_uuid
            params = '"?re=%s&rr=%s&tt=%s&id=%s' % (
                html_escape(html_escape(supplier_rfc or '')),
                html_escape(html_escape(customer_rfc or '')),
                total or 0.0, uuid or '')
            try:
                response = Client(url).service.Consulta(params).Estado
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            rec.l10n_mx_edi_sat_status = CFDI_SAT_QR_STATE.get(response.__repr__(), 'none')

    
    def _set_cfdi_origin(self, uuid):
        """Try to write the origin in of the CFDI, it is important in order
        to have a centralized way to manage this elements due to the fact
        that this logic can be used in several places functionally speaking
        all around Odoo.
        :param uuid:
        :return:
        """
        self.ensure_one()
        origin = '04|%s' % uuid
        self.update({'l10n_mx_edi_origin': origin})
        return origin

    
    def action_draft(self):
        for record in self.filtered('l10n_mx_edi_cfdi_uuid'):
            record.l10n_mx_edi_origin = self._set_cfdi_origin(record.l10n_mx_edi_cfdi_uuid)
        return super(HRPayslip, self).action_draft()
    
    
    
    def action_payslip_draft(self):
        if any(rec.l10n_mx_edi_cfdi_uuid for rec in self):
            raise UserError(_("Advertencia !!!\n\nNo es posible regresar a Borrador cuando ya se hizo el proceso de Timbrado y Cancelación."))                
        return super(HRPayslip,self).action_payslip_draft()

    
    
    
