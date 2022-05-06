# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
#import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import zipfile
import base64
from xml.dom.minidom import parse, parseString
import time
import tempfile
import os
import io
import xmltodict
import codecs
from xml.dom import minidom
from datetime import datetime, timedelta
import time
from suds.client import Client, WebFault
#import suds
import qrcode
from suds.plugin import MessagePlugin
import logging
_logger = logging.getLogger(__name__)

class LogPlugin(MessagePlugin):
    def sending(self, context):
        _logger.info(str(context.envelope))
        #print(str(context.envelope))
        return
    def received(self, context):
        _logger.info(str(context.reply))
        #print(str(context.reply))
        return

production_url  = 'https://sat.sifei.com.mx:8443/SIFEI/SIFEI?wsdl'
testing_url     = 'http://devcfdi.sifei.com.mx:8080/SIFEI33/SIFEI?wsdl'
production_cancel_url  = 'https://sat.sifei.com.mx:9000/CancelacionSIFEI/Cancelacion?wsdl'
testing_cancel_url     = 'http://devcfdi.sifei.com.mx:8888/CancelacionSIFEI/Cancelacion?wsdl'
    
    

class HRPayslip(models.Model):
    _inherit = 'hr.payslip'
    
    cfdi_pac = fields.Selection(selection_add=[('pac_sifei', 'SIFEI - https://www.sifei.com.mx')], string='CFDI Pac', 
                                readonly=True, store=True, copy=False, default='pac_sifei',
                                ondelete={'sifei': 'set null'})
    
    def add_addenda_xml(self, xml_res_str=None, comprobante=None):
        return xml_res_str
        
        
    
    def write_cfd_data(self, cfd_datas):
        cfd_datas = cfd_datas or {}
        comprobante = 'cfdi:Comprobante'
        data = {}

        cfd_data = cfd_datas
        NoCertificado = cfd_data.get(comprobante, {}).get('@NoCertificado', '')
        certificado = cfd_data.get(comprobante, {}).get('@Certificado', '')
        sello = cfd_data.get(comprobante, {}).get('@Sello', '')
        cadena_original = cfd_data.get('@cadena_original', '')
        data = {
            'no_certificado': NoCertificado,
            'certificado': certificado,
            'sello': sello,
            'cadena_original': cadena_original,
        }
        self.write(data)
        return True
    
    
    def get_driver_cfdi_sign(self):
        factura_mx_type__fc = super(HRPayslip, self).get_driver_cfdi_sign()
        if factura_mx_type__fc == None:
            factura_mx_type__fc = {}
        factura_mx_type__fc.update({'pac_sifei': self.action_get_stamp_sifei})
        return factura_mx_type__fc
    
    
    def get_driver_cfdi_cancel(self):
        factura_mx_type__fc = super(HRPayslip, self).get_driver_cfdi_cancel()
        if factura_mx_type__fc == None:
            factura_mx_type__fc = {}
        factura_mx_type__fc.update({'pac_sifei': self.action_cancel_stamp_sifei})
        return factura_mx_type__fc

    
    
    def action_cancel_stamp_sifei(self):
        msg = ''
        if (self.company_id.pac_testing and self.company_id.pac_user_4_testing and \
            self.company_id.pac_password_4_testing and  self.company_id.pac_equipo_id_4_testing) or \
            (not self.company_id.pac_testing and self.company_id.pac_user and \
             self.company_id.pac_password and self.company_id.pac_equipo_id):
            file_globals = self._get_file_globals()
            user        = self.company_id.pac_testing and self.company_id.pac_user_4_testing or self.company_id.pac_user
            password    = self.company_id.pac_testing and self.company_id.pac_password_4_testing or self.company_id.pac_password
            equipo_id   = self.company_id.pac_testing and self.company_id.pac_equipo_id_4_testing or self.company_id.pac_equipo_id
            wsdl_url    = self.company_id.pac_testing and testing_cancel_url or production_cancel_url
            fname_pfx = open(file_globals['fname_pfx'], "rb")
            certificate_pfx = fname_pfx.read()
            fname_pfx.close()
            certificate_pfx = self.journal_id.certificate_pfx_file.decode("utf-8")
            client = Client(wsdl_url, plugins=[LogPlugin()])
            try:
                params = '|%s|%s||' % (self.cfdi_folio_fiscal, self.cfdi_motivo_cancelacion)
                resultado = client.service.cancelaCFDI(user, password, self.company_id.partner_id.vat,
                                                       certificate_pfx, file_globals['password'], params) #self.cfdi_folio_fiscal)
            except WebFault as f:
                raise UserError(_('Advertencia !!!\nOcurrió un error al intentar Cancelar el Timbre. \n\nCódigo: %s\nError: %s\nMensaje: %s') % 
                                (f.fault.detail.SifeiException.codigo,f.fault.detail.SifeiException.error, f.fault.detail.SifeiException.message))
            
            msg += _('Resultado: %s') % (resultado)
        else:
            msg = _('No se configuró correctamente los datos del Webservice del PAC, revise los parámetros del PAC')
        return {'message': msg, 'status_uuid': self.cfdi_folio_fiscal, 'status': True}
    
    
    
    def action_get_stamp_sifei(self, fdata=None):
        context = self._context.copy() or {}
        invoice = self
        invoice_obj = self.env['account.move']
        comprobante = 'cfdi:Comprobante'
        cfd_data = base64.decodestring(fdata or self.xml_file_no_sign_index)
        xml_res_str = parseString(cfd_data)
        xml_res_addenda = self.add_addenda_xml(xml_res_str, comprobante)
        xml_res_str_addenda = xml_res_addenda.toxml('UTF-8')
        xml_res_str_addenda = xml_res_str_addenda.replace(codecs.BOM_UTF8, b'')
        ###############################
        file = False
        msg = ''
        cfdi_xml = False
        
        if (self.company_id.pac_testing and self.company_id.pac_user_4_testing and \
            self.company_id.pac_password_4_testing and  self.company_id.pac_equipo_id_4_testing) or \
            (not self.company_id.pac_testing and self.company_id.pac_user and \
             self.company_id.pac_password and self.company_id.pac_equipo_id):
            file_globals = self._get_file_globals()
            user        = self.company_id.pac_testing and self.company_id.pac_user_4_testing or self.company_id.pac_user
            password    = self.company_id.pac_testing and self.company_id.pac_password_4_testing or self.company_id.pac_password
            equipo_id   = self.company_id.pac_testing and self.company_id.pac_equipo_id_4_testing or self.company_id.pac_equipo_id
            wsdl_url    = self.company_id.pac_testing and testing_url or production_url
            
            if 'devcfdi' in wsdl_url:
                msg += _('ADVERTENCIA, TIMBRADO EN PRUEBAS!!!!\n\n')

            # -.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-    
            ## Archivo a Timbrar ###
            (fileno, fname_xml) = tempfile.mkstemp(".xml", "odoo_xml_payslip_to_sifei__")
            f_argil = open(fname_xml, 'wb')
            #f_argil.write(xml_res_str_addenda.decode("utf-8"))
            f_argil.write(xml_res_str_addenda)
            f_argil.close()
            os.close(fileno)

            xres = os.system("zip -j " + fname_xml.split('.')[0] + ".zip " + fname_xml + " > /dev/null")
            
            zipped_xml_file = open(fname_xml.split('.')[0] + ".zip", 'rb')
            cfdi_zipped = base64.b64encode(zipped_xml_file.read())
            zipped_xml_file.close()

            client = Client(wsdl_url, plugins=[LogPlugin()])
            w,f = False, False
            try:
                resultado = client.service.getCFDI(user, password, cfdi_zipped.decode("utf-8"), ' ', equipo_id)
            except WebFault as w:
                f = w

            if f:
                raise UserError(_('Advertencia !!!\nOcurrió un error al intentar obtener el Timbre. \n\nCódigo: %s\nError: %s\nMensaje: %s') % 
                                (f.fault.detail.SifeiException.codigo,f.fault.detail.SifeiException.error, f.fault.detail.SifeiException.message))
                
            #fname_stamped_zip = invoice_obj.binary2file(b'', b'odoo_' + str.encode(self.fname_payslip) + b'_stamped', b'.zip')
            
            fstamped = io.BytesIO(base64.b64decode(str.encode(resultado)))
            
            zipf = zipfile.ZipFile(fstamped, 'r')
            zipf1 = zipf.open(zipf.namelist()[0])
            xml_timbrado_str = zipf1.read().replace(b'\r',b'').replace(b'\n',b'')
            xml_timbrado = parseString(xml_timbrado_str)
            timbre = xml_timbrado.getElementsByTagName('tfd:TimbreFiscalDigital')[0]
                
            # -.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-.-
            htz=abs(int(self._get_time_zone()))
            mensaje = 'Proceso de timbrado exitoso...'
            folio_fiscal = timbre.attributes['UUID'].value            
            fecha_timbrado = timbre.attributes['FechaTimbrado'].value or False
            fecha_timbrado = fecha_timbrado and time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(fecha_timbrado[:19], '%Y-%m-%dT%H:%M:%S')) or False
            fecha_timbrado = fecha_timbrado and datetime.strptime(fecha_timbrado, '%Y-%m-%d %H:%M:%S') + timedelta(hours=htz) or False
            cfdi_no_certificado = timbre.attributes['NoCertificadoSAT'].value
            cfdi_cbb = invoice_obj.create_qr_image(cfd_data, self.neto_a_pagar, timbre.attributes['UUID'].value)
            cfdi_sello =  timbre.attributes['SelloSAT'].value
            cfdi_data = {
                'cfdi_cbb': cfdi_cbb or False,
                'cfdi_sello': cfdi_sello or False,
                'sello'     : cfdi_sello or False,
                'cfdi_no_certificado': cfdi_no_certificado or False,
                'cfdi_fecha_timbrado': fecha_timbrado,
                'cfdi_xml': xml_timbrado_str, 
                'cfdi_folio_fiscal': folio_fiscal,
            }
            msg += mensaje + ". Folio Fiscal: " + folio_fiscal + "."
            msg += _(u"\nPor favor asegúrese que la estructura del XML de la factura ha sido generada correctamente en el SAT\nhttps://www.consulta.sat.gob.mx/sicofi_web/moduloECFD_plus/ValidadorCFDI/Validador%20cfdi.html")
            if cfdi_data.get('cfdi_xml', False):
                file = base64.encodestring(cfdi_data['cfdi_xml'] or '')
                cfdi_xml = cfdi_data.pop('cfdi_xml')
            if cfdi_xml:
                self.write(cfdi_data)
                self.write_cfd_data(xmltodict.parse(cfdi_xml))
                cfdi_data['cfdi_xml'] = cfdi_xml
            else:
                raise UserError(_('Advertencia !!!\nOcurrió un error al intentar timbrar, por favor revise el LOG'))
        else:
            msg += 'No se encontró información del PAC, revise la configuración'
            raise UserError(_('Advertencia !!!\nNo se encontró información del Webservice del PAC, revise la configuración'))
        #raise osv.except_osv('Pausa','Pausa')
        return {'file': file, 'msg': msg, 'cfdi_xml': cfdi_xml}

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    
