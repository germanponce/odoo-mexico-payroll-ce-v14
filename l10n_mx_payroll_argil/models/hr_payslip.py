# -*- encoding: utf-8 -*-
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, timedelta, date
import time
import pytz
import base64
import xml
import codecs
import traceback
import os
import tempfile
from lxml import etree
from lxml.objectify import fromstring
import logging
_logger = logging.getLogger(__name__)

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

class SatPayslipCFDIRel(models.Model):
    _name = 'sat.payslip.cfdi.rel'
    _description = 'Relacion de CFDI'
    _rec_name = 'payslip_id' 

    payslip_id = fields.Many2one('hr.payslip', 'Nómina', required=True)
    payslip_rel_id = fields.Many2one('hr.payslip', 'ID Rel')
    


class HRPayslip(models.Model):
    _inherit = ['hr.payslip', 'mail.thread']
    _name="hr.payslip"
    
    
    
    @api.depends('journal_id')
    def _get_address_issued_payroll(self):
        for rec in self:
            rec.address_issued_id = rec.journal_id.address_invoice_company_id or \
                                    (rec.journal_id.company2_id and rec.journal_id.company2_id.address_invoice_parent_company_id) or \
                                    rec.journal_id.company_id.address_invoice_parent_company_id or False
            rec.company_emitter_id = rec.journal_id.company2_id or rec.journal_id.company_id or False

    
    address_issued_id = fields.Many2one('res.partner', compute='_get_address_issued_payroll', 
                                        string='Dirección Emisión', store=True,
                                        help='This address will be used as address that issued for electronic invoice')
    
    company_emitter_id = fields.Many2one('res.company', compute='_get_address_issued_payroll', store=True,
                                         string='Compañía Emisora', 
                                         help='This company will be used as emitter company in the electronic invoice')    
    
    cfdi_pac                = fields.Selection([], string='PAC', readonly=True, store=True, copy=False)
    ##################################
    type_rel_cfdi_ids = fields.One2many('sat.payslip.cfdi.rel', 'payslip_rel_id', 'CFDI Relacionados',
                                        states={'draft': [('readonly', False)]}, readonly=True,) 
    type_rel_id = fields.Selection([('na','No Aplica'),
                                    ('04','Sustitución de los CFDI previos')],
                                    default='na', string="Tipo relación CFDI",
                                    states={'draft': [('readonly', False)]}, readonly=True,)


    def get_driver_cfdi_sign(self):
        """function to inherit from module driver of pac and add particular function"""
        return {}

    
    def get_driver_cfdi_cancel(self):
        """function to inherit from module driver of pac and add particular function"""
        return {}
    
    
    def _get_file_globals(self):
        ctx = self._context.copy()
        file_globals = {}
        inv_obj = self.env['account.move']
        payslip = self[0]
        ctx.update({'date_work': payslip.date_payslip_tz})

        if not (payslip.journal_id.date_start <= payslip.date_payslip_tz.date() and payslip.journal_id.date_end >= payslip.date_payslip_tz.date()):
            raise UserError(_("Error !!!\nLa fecha de la factura está fuera del rango de Vigencia del Certificado, por favor revise."))
        
        
        certificate_file_pem     = payslip.journal_id.certificate_file_pem
        certificate_key_file_pem = payslip.journal_id.certificate_key_file_pem
        certificate_file         = payslip.journal_id.certificate_file
        certificate_key_file     = payslip.journal_id.certificate_key_file
        certificate_pfx_file     = payslip.journal_id.certificate_pfx_file
        
        
        fname_cer_pem = False
        try:
            fname_cer_pem = inv_obj.binary2file(
                certificate_file_pem, 'odoo_' + (
                payslip.journal_id.serial_number or '') + '__certificate__',
                '.cer.pem')
        except:
            raise UserError(_("Error !!! \nEl archivo del Certificado no existe en formato PEM"))
        
        file_globals['fname_cer'] = fname_cer_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_key_pem = False
        try:
            fname_key_pem = inv_obj.binary2file(
                certificate_key_file_pem, 'odoo_' + (
                payslip.journal_id.serial_number or '') + '__certificate__',
                '.key.pem')
        except:
            raise UserError(_("Error !!! \nEl archivo de la llave (KEY) del Certificado no existe en formato PEM"))

        file_globals['fname_key'] = fname_key_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_cer_no_pem = False
        try:
            fname_cer_no_pem = inv_obj.binary2file(
                certificate_file, 'odoo_' + (
                payslip.journal_id.serial_number or '') + '__certificate__',
                '.cer')
        except:
            pass
        file_globals['fname_cer_no_pem'] = fname_cer_no_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_key_no_pem = False
        try:
            fname_key_no_pem = inv_obj.binary2file(
                certificate_key_file, 'odoo_' + (
                payslip.journal_id.serial_number or '') + '__certificate__',
                '.key')
        except:
            pass
        file_globals['fname_key_no_pem'] = fname_key_no_pem
        # - - - - - - - - - - - - - - - - - - - - - - -
        fname_pfx = False
        try:
            fname_pfx = inv_obj.binary2file(
                certificate_pfx_file, 'odoo_' + (
                payslip.journal_id.serial_number or '') + '__certificate__',
                '.pfx')
        except:
            raise UserError(_("Error !!! \nEl archivo del Certificado no existe en formato PFX"))

        file_globals['fname_pfx'] = fname_pfx
        # - - - - - - - - - - - - - - - - - - - - - - -
        file_globals['password'] = payslip.journal_id.certificate_password
        # - - - - - - - - - - - - - - - - - - - - - - -
        if payslip.journal_id.fname_xslt:
            if (payslip.journal_id.fname_xslt[0] == os.sep or \
                payslip.journal_id.fname_xslt[1] == ':'):
                file_globals['fname_xslt'] = payslip.journal_id.fname_xslt
            else:
                file_globals['fname_xslt'] = os.path.join(
                    tools.config["root_path"], payslip.journal_id.fname_xslt)
        else:
            # Search char "," for addons_path, now is multi-path
            all_paths = tools.config["addons_path"].split(",")
            for my_path in all_paths:
                if payslip.company_id.version_de_cfdi_para_nominas=='3.3' and os.path.isdir(os.path.join(my_path, 'l10n_mx_einvoice', 'SAT')):
                    # If dir is in path, save it on real_path
                    file_globals['fname_xslt'] = my_path and os.path.join(
                        my_path, 'l10n_mx_einvoice', 'SAT', 'cadenaoriginal_3_3',
                        'cadenaoriginal_3_3.xslt') or ''
                    ### TFD CADENA ORIGINAL XSLT ###
                    file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                        my_path, 'l10n_mx_einvoice', 'SAT', 'cadenaoriginal_3_3',
                        'cadenaoriginal_TFD_1_1.xslt') or ''
                    break
                elif payslip.company_id.version_de_cfdi_para_nominas=='4.0' and os.path.isdir(os.path.join(my_path, 'l10n_mx_payroll_argil', 'data', 'xslt')):
                    # If dir is in path, save it on real_path
                    file_globals['fname_xslt'] = my_path and os.path.join(
                        my_path, 'l10n_mx_payroll_argil', 'data', 'xslt','cadenaoriginal_4_0.xslt') or ''
                    ### TFD CADENA ORIGINAL XSLT ###
                    file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                        my_path, 'l10n_mx_payroll_argil', 'data', 'xslt', 'cadenaoriginal_TFD_1_1.xslt') or ''
                    break
                    
        if not file_globals.get('fname_xslt', False):
            raise UserError(_("Advertencia !!! \nNo se tiene definido fname_xslt"))

        if not os.path.isfile(file_globals.get('fname_xslt', ' ')):
            raise UserError(_("Advertencia !!! \nNo existe el archivo [%s]. !") % (file_globals.get('fname_xslt', ' ')))

        file_globals['serial_number'] = payslip.journal_id.serial_number
        # - - - - - - - - - - - - - - - - - - - - - - -

        # Search char "," for addons_path, now is multi-path
        all_paths = tools.config["addons_path"].split(",")
        for my_path in all_paths:
            if payslip.company_id.version_de_cfdi_para_nominas=='3.3' and os.path.isdir(os.path.join(my_path, 'l10n_mx_einvoice', 'SAT')):
                # If dir is in path, save it on real_path
                file_globals['fname_xslt'] = my_path and os.path.join(
                    my_path, 'l10n_mx_einvoice', 'SAT','cadenaoriginal_3_3', 'cadenaoriginal_3_3.xslt') or ''
                ### TFD CADENA ORIGINAL XSLT ###
                file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                    my_path, 'l10n_mx_einvoice', 'SAT', 'cadenaoriginal_3_3', 'cadenaoriginal_TFD_1_1.xslt') or ''
            elif payslip.company_id.version_de_cfdi_para_nominas=='4.0' and os.path.isdir(os.path.join(my_path, 'l10n_mx_payroll_argil', 'data', 'xslt')):
                # If dir is in path, save it on real_path
                file_globals['fname_xslt'] = my_path and os.path.join(
                    my_path, 'l10n_mx_payroll_argil', 'data','xslt', 'cadenaoriginal_4_0.xslt') or ''
                ### TFD CADENA ORIGINAL XSLT ###
                file_globals['fname_xslt_tfd'] = my_path and os.path.join(
                    my_path, 'l10n_mx_payroll_argil', 'data', 'xslt', 'cadenaoriginal_TFD_1_1.xslt') or ''
        return file_globals
    
    
    def _get_cfdi_data_dict(self):
            
        emisor_rfc = self.company_id.partner_id.vat
        emisor_regimen = self.company_id.regimen_fiscal_id.code
        receptor_rfc = self.employee_id.address_home_id.vat
        
        # Validaciones:
        error = False
        if not self.company_id.registro_patronal:
            error = _("Advertencia !!!\nNo ha definido el Registro Patronal del Emisor, por favor configure ese dato y reintente la operación")
        if not emisor_rfc:
            error = _("Advertencia !!!\nNo ha definido el RFC del Emisor, por favor configure ese dato y reintente la operación")
        if not receptor_rfc:
            error = _("Advertencia !!!\nNo ha definido el RFC del Receptor [%s] %s, por favor configure ese dato y reintente la operación") % (self.employee_id.id, self.employee_id.name)
        #if not self.employee_id.bank_account_id.acc_number:
        #    error = _("Advertencia !!!\nNo ha definido la cuenta Bancaria del Trabajador [%s] %s, por favor configure ese dato y reintente la operación") % (self.employee_id.id, self.employee_id.name)
        if not self.employee_id.address_home_id.state_id:
            error = _("Advertencia !!!\nNo ha definido el Estado en la dirección del Trabajador [%s] %s, por favor configure ese dato y reintente la operación") % (self.employee_id.id, self.employee_id.name)
        if not self.employee_id.num_empleado:
            error = _("Advertencia !!!\nNo ha definido el Número de Empleado del Trabajador [%s] %s, por favor configure ese dato y reintente la operación") % (self.employee_id.id, self.employee_id.name)
        if self.contract_id.date_start > self.date_to:
            error = _("Advertencia !!!\nLa fecha inicial de Relación Laboral (Contrato => Fecha Inicial) no es menor o igual a la Fecha Final del Periodo de Pago para el Trabajador [%s] %s") % (self.employee_id.id, self.employee_id.name)
        
        if error:
            raise ValidationError(error)
            
        contract = self.contract_id
        
        
        if not (contract.sat_periodicidadpago_id and contract.sat_riesgopuesto_id and \
                contract.sat_tiporegimen_id and contract.sat_tipojornada_id and \
                contract.sindicalizado and contract.sat_tipo_contrato_id):
            raise UserError(_("Advertencia !!!\nFalta información en el Contrato del Trabajador %s, por favor configure ese dato y re-intente la operación") % contract.name) 
        
        emisor_rfc = emisor_rfc.replace('&','&amp;')
        receptor_rfc = receptor_rfc.replace('&','&amp;')
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
        
        fecha = time.strftime('%Y-%m-%dT%H:%M:%S', time.strptime(str(self.date_payslip_tz)[:19], '%Y-%m-%d %H:%M:%S'))
        return {'o'             : self,
                'emisor_rfc'    : emisor_rfc,
                'emisor_nombre' : emisor_nombre,
                'emisor_regimen': emisor_regimen,
                'receptor_rfc'  : receptor_rfc,
                'receptor_nombre': receptor_nombre,
                'fecha'         : fecha,
                'error'         : error,
               }
    
    
    
    def get_xml_to_sign(self):
        '''Creates and returns a dictionnary containing 'cfdi' if the cfdi is well created, 'error' otherwise.
        '''
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        
        self.payslip_datetime = fields.datetime.now()
        values = self._get_cfdi_data_dict()
        if 'error' in values and values['error']:
            self.message_post(body="Error al generar CFDI\n\n" + values['error'])
            return False

        account_move_obj = self.env['account.move']
        if not self.journal_id.use_for_cfdi:
            self.message_post(body=_("No se generó CFDI. El Diario Contable asociado a este registro indica que no se debe usar para generar CFDI. Si considera incorrecto revise su configuración."))
            return False
        context = self._context and dict(self._context.copy()) or {}
        context.update(self._get_file_globals())
        if 'error' in context: # Revisamos si se cargan los archivos del CSD necesarios para generar el Sello del CFDI
            self.message_post(body="Error al generar CFDI" + context['error'])
            return False
        cert_str = account_move_obj._get_certificate_str(context['fname_cer'])
        if not cert_str: # Validamos si el Certificado se cargo correctamente
            self.message_post(body=_("Error al generar CFDI\n\nError en Certificado !!!\nNo puedo obtener el Certificado de Sello Digital para generar el CFDI. Revise su configuración."))
            return False
        cert_str = cert_str.replace('\n\r', '').replace('\r\n', '').replace('\n', '').replace('\r', '').replace(' ', '')
        noCertificado = self.journal_id.serial_number #account_move_obj._get_noCertificado(context['fname_cer'])        
        if not noCertificado: # Validamos si el Numero de Certificado se cargo correctamente
            self.message_post(body=_("Error al generar CFDI\n\nError !!!\n\nNo se pudo obtener el Número de Certificado de Sello Digital para generar el CFDI. Por favor revise la configuración del Diario Contable"))
            return False

        values.update({'certificate_number' : noCertificado,
                       'certificate'        : cert_str,
                       })
        
        if self.company_id.version_de_cfdi_para_nominas=='3.3':
            cfdi = qweb._render('l10n_mx_payroll.cfdi33_nomina12', values=values)
        elif self.company_id.version_de_cfdi_para_nominas=='4.0':
            cfdi = qweb._render('l10n_mx_payroll_argil.cfdi40_nomina12', values=values)
        _logger.info("cfdi: %s" % cfdi)
        (fileno_xml, fname_xml) = tempfile.mkstemp('.xml', 'odoo_' + '__nomina__')        
        os.close(fileno_xml)
        with open(fname_xml, 'bw') as new_xml:
            new_xml.write(cfdi)

        with open(fname_xml,'rb') as b:
            data_xml = b.read()
        b.close()

        fname_txt = fname_xml.replace('.','_') + '.txt'
        (fileno_sign, fname_sign) = tempfile.mkstemp('.txt', 'odoo_' + '__nomina_txt_md5__')
        os.close(fileno_sign)
        context.update({
            'fname_xml'  : fname_xml,
            'fname_txt'  : fname_txt,
            'fname_sign' : fname_sign,
        })
        context.update({'fecha'     : time.strftime('%Y-%m-%dT%H:%M:%S', time.strptime(str(self.date_payslip_tz)[:19], '%Y-%m-%d %H:%M:%S')) or '',
                        'xml_prev'  : data_xml }) # doc_xml_full
        txt_str = account_move_obj.with_context(context)._xml2cad_orig()
        if not txt_str:
            self.message_post(body=_("Error al generar CFDI\n\nError en la Cadena Original !!!\nNo puedo obtener la Cadena Original del Comprobante.\n"
                                   "Revise su configuración."))
            return False
        context.update({'cadena_original': txt_str})
        self.write({'cfdi_cadena_original':txt_str, 'no_certificado': noCertificado})
        sign_str = account_move_obj.with_context(context)._get_sello()

        data_xml = data_xml.replace(b'Sello=""', b'Sello="%s"' % str.encode(sign_str))
        return data_xml

    @api.model
    def get_cfdi_cadena(self, xslt_path, cfdi_as_tree):
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.model
    def _get_einvoice_cadena_tfd(self, cfdi_signed):
        self.ensure_one()
        #get the xslt path
        file_globals = self._get_file_globals()
        if 'fname_xslt_tfd' in file_globals:
            xslt_path = file_globals['fname_xslt_tfd']
        else:
            raise UserError("Errr!\nNo existe en archivo XSLT TFD en la carpeta SAT.")
        #get the cfdi as eTree
        #cfdi = str.encode(cfdi_signed)
        cfdi = fromstring(cfdi_signed)
        cfdi = self.env['account.move'].account_invoice_tfd_node(cfdi)
        #return the cadena
        return self.get_cfdi_cadena(xslt_path, cfdi)    
        
        
    
    def get_cfdi(self):
        attachment_obj = self.env['ir.attachment']
        if not self:
            return True
        
        type__fc = self[0].get_driver_cfdi_sign() # Instanciamos la clase para la integración con el PAC
        
        if self[0].cfdi_pac not in type__fc.keys(): # No hay Conector a PAC instalado
            self.message_post(body=_("Error al generar CFDI\n\nNo se encontró el Conector del PAC para %s") % pac_type)
            return True
        pac_type = self[0].cfdi_pac

        for payslip in self.filtered(lambda w: (w.payslip_run_id and w.payslip_run_id.cfdi_timbrar) or w.cfdi_timbrar):
            payslip.write({'payslip_datetime' : fields.Datetime.now(),
                           'user_id'          : self.env.user.id,})

            fname_payslip = payslip.fname_payslip
            cfdi_state = payslip.cfdi_state
            if cfdi_state =='draft':
                xml_data = payslip.get_xml_to_sign()
                if not xml_data:
                    payslip.message_post(body=_("Error al generar CFDI\n\nNo se pudo crear el archivo XML para enviar al PAC, revise el LOG"))
                    continue
                payslip.write({'xml_file_no_sign_index': xml_data,
                               'cfdi_state'            : 'xml_unsigned',
                              })
                cfdi_state = 'xml_unsigned'
            # Mandamos a Timbrar
            if cfdi_state =='xml_unsigned' and not payslip.xml_file_signed_index:
                try:
                    index_xml = ''
                    msj = ''
                    fname_payslip = payslip.fname_payslip and payslip.fname_payslip + '.xml' or ''
                    if not 'xml_data' in locals():
                        xml_data = payslip.get_xml_to_sign()
                        _logger.info('Re-intentando generar XML para timbrar - Nomina: %s', fname_payslip)
                        if not xml_data:
                            payslip.write({'xml_file_no_sign_index': xml_data,
                                           'cfdi_state'            : 'xml_unsigned',
                                          })
                            continue
                    else:
                        _logger.info('Listo archivo XML a timbrar en el PAC - Recibo de Nómina: %s', fname_payslip)

                    fdata = base64.encodebytes(xml_data)
                    _logger.info('Solicitando a PAC el Timbre para Recibo de Nómina CFDI: %s', fname_payslip)
                    res = type__fc[pac_type](fdata) #
                    
                    _logger.info('Timbre entregado por el PAC - Recibo de Nómina CFDI: %s', fname_payslip)

                    msj = tools.ustr(res.get('msg', False))
                    index_xml = res.get('cfdi_xml', False)
                    if isinstance(index_xml, str):
                        index_xml = str.encode(index_xml)
                    payslip.write({'xml_file_signed_index' : index_xml})
                    ###### Recalculando la Cadena Original ############
                    cfdi_signed = fdata
                    cadena_tfd_signed = ""
                    try:
                        cadena_tfd_signed = payslip._get_einvoice_cadena_tfd(index_xml)
                    except:
                        cadena_tfd_signed = payslip.cfdi_cadena_original
                    payslip.cfdi_cadena_original = cadena_tfd_signed
                    ################ FIN ################
                    data_attach = {
                            'name'        : fname_payslip,
                            'datas'       : base64.encodebytes(index_xml),
                            'store_fname' : fname_payslip,
                            'description' : 'Archivo XML del Recibo de Nomina CFDI: %s' % (payslip.name),
                            'res_model'   : 'hr.payslip',
                            'res_id'      : payslip.id,
                            'type'        : 'binary',
                        }
                    attach = attachment_obj.with_context({}).create(data_attach)
                    xres = payslip.do_something_with_xml_attachment(attach)
                    cfdi_state = 'xml_signed'
                    payslip.message_post(subject="CFDI generado exitosamente",
                                         body=msj)
                except Exception:
                    xerror = tools.ustr(traceback.format_exc())
                    payslip.message_post(body=_("Error al generar CFDI\n\n") + xerror)
                    self.env.cr.commit()
                    _logger.error(xerror)
                    continue
                payslip.write({'cfdi_state': 'xml_signed'})
                self.env.cr.commit()
            # Generamos formato de Impresión
            if cfdi_state == 'xml_signed' or payslip.xml_file_signed_index:
                _logger.info('Generando PDF - Recibo de Nómina CFDI: %s', fname_payslip)
                cfdi_state = 'pdf'                
                _logger.info('PDF generado - Recibo de Nómina CFDI: %s', fname_payslip)
                payslip.write({'cfdi_state': 'pdf'})

            # ARGIL ARGIL
            
            if cfdi_state == 'pdf' and payslip.employee_id.address_home_id.envio_manual_cfdi:
                payslip.message_post(body=_('Envío de CFDI por Correo electrónico\n\nNo se enviaron los archivos por correo porque el Partner está marcado para no enviar automáticamente los archivos del CFDI (XML y PDF)'))
                payslip.write({'cfdi_state': 'sent'})
                cfdi_state == 'sent'
            # Enviamos al cliente los archivos de la factura
            elif cfdi_state == 'pdf' and not payslip.employee_id.address_home_id.envio_manual_cfdi:
                _logger.info('Intentando enviar XML y PDF al mail del Empleado - Nomina: %s', fname_payslip)
                msj = ''
                state = ''
                partner_mail = payslip.employee_id.address_home_id.email or False
                user_mail = self.env.user.email or False
                company_id = payslip.company_id.id
                address_id = payslip.employee_id.address_home_id.address_get(['invoice'])['invoice']
                partner_invoice_address = address_id
                fname_payslip = payslip.fname_payslip or ''
                adjuntos = attachment_obj.search([('res_model', '=', 'hr.payslip'), 
                                                  ('res_id', '=', payslip.id)])
                q = True
                attachments = []
                for attach in adjuntos:
                    if q and attach.name.endswith('.xml'):
                        attachments.append(attach.id)
                        break

                mail_compose_message_pool = self.env['mail.compose.message']

                template_id = self.env['mail.template'].search([('model_id.model', '=', 'hr.payslip'),
                                                                #('company_id','=', company_id),
                                                                #('report_template.report_name', '=',report_name)
                                                               ], limit=1)                            
                if not template_id:
                    payslip.message_post(body=_('Error en Envío de CFDI por Correo electrónico\n\nNo se pudo enviar los archivos por correo porque no tiene configurada la Plantilla de Correo Electrónico'))
                    continue

                ctx = dict(
                    default_model='hr.payslip',
                    default_res_id=payslip.id,
                    default_use_template=bool(template_id),
                    default_template_id=template_id.id,
                    default_composition_mode='comment',
                )
                ## CHERMAN 
                context2 = dict(self._context)
                if 'default_journal_id' in context2:
                    del context2['default_journal_id']
                if 'default_type' in context2:
                    del context2['default_type']
                if 'search_default_dashboard' in context2:
                    del context2['search_default_dashboard']

                try:
                    xres = mail_compose_message_pool.with_context(context2).onchange_template_id(template_id=template_id.id, composition_mode=None,model='hr.payslip', res_id=payslip.id)
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
                except:
                    payslip.message_post(body=_('No se genero el PDF del CFDI de Nómina, no se enviará al Empleado. - Nomina: %s') % fname_payslip)
                    _logger.error('No se genero el PDF del CFDI, no se enviara al Empleado. - Nomina: %s', fname_payslip)
                    continue
                xres['value'].update({'attachment_ids' : [(6, 0, attachments)]})
                message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
                _logger.info('Antes de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
                xx = message.action_send_mail()
                _logger.info('Despues de  enviar XML y PDF por mail al Empleado. - Nomina: %s', fname_payslip)
                payslip.write({'cfdi_state': 'sent'})
                payslip.message_post(body=_("El CFDI fue enviado exitosamente por correo electrónico..."))
                cfdi_state == 'sent'

            _logger.info('Fin proceso Timbrado - Recibo de Nómina CFDI: %s', fname_payslip)

            # Se encontraron que los archivos PDF se duplican
            adjuntos2 = attachment_obj.search([('res_model', '=', 'hr.payslip'), ('res_id', '=', payslip.id)])
            x = 0
            for attach in adjuntos2:
                if attach.name.endswith('.pdf'):
                    x and attach.unlink()
                    if x: 
                        break
                    x += 1
        return True
    
    
    
    def action_payslip_draft(self):
        if any(rec.cfdi_folio_fiscal for rec in self):
            raise UserError(_("Advertencia !!!\n\nNo es posible regresar a Borrador cuando ya se hizo el proceso de Timbrado y Cancelación."))                
        return super(HRPayslip,self).action_payslip_draft()
    
    
    
    def action_cancel(self):
        if not self._context.get('settlement_id', False) and any(x.settlement_id for x in self):
            raise UserError(_("Advertencia !\nNo es posible cancelar una Nómina que fue generada desde un finiquito"))
        if self and not self[0].cfdi_motivo_cancelacion:
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
        moves.filtered(lambda x: x.state == 'posted').button_cancel()
        try:
            moves.unlink()
        except:
            pass
        type__fc = self and self[0].get_driver_cfdi_cancel() or False
        if not type__fc:
            return self.write({'state': 'cancel'})

        for payslip in self:
            if not payslip.cfdi_folio_fiscal or not payslip.journal_id.use_for_cfdi:
                continue
            type__fc = payslip.get_driver_cfdi_cancel()
            if not type__fc or (not payslip.cfdi_pac in type__fc.keys()):
                payslip.message_post(body=_("""El CFDI NO fue cancelado porque el PAC no estaba configurado correctamente\n\n"""
                                            """Proceda a cancelar el CFDI en el portal del SAT."""))
                continue            

            res2 = type__fc[payslip.cfdi_pac]()
            payslip.message_post(body=_("""El CFDI fue cancelado exitosamente...\n\n"""
                                        """Mensaje: %s\n\nCódigo: %s""") % (res2['message'], res2['status_uuid']))
            payslip.write({'cfdi_fecha_cancelacion':time.strftime('%Y-%m-%d %H:%M:%S'),})
        return self.write({'state': 'cancel', 'payslip_run_id' : False})