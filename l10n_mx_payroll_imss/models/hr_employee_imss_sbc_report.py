# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools
import base64
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import xlsxwriter
from io import BytesIO
from tempfile import NamedTemporaryFile
import logging
_logger = logging.getLogger(__name__)

bimestre = {1  : '1', 2  : '1',
            3  : '2', 4  : '2',
            5  : '3', 6  : '3',
            7  : '4', 8  : '4',
            9  : '5', 10 : '5',
            11 : '6', 12 : '6',
           }

tipo_salario = {'0' : 'Fijo',
                '1' : 'Variable',
                '2' : 'Mixto'}
    
class HREmployeeIMSSSSBC(models.Model):
    _inherit="hr.employee.imss.sbc"
    
    filename= fields.Char(string='Nombre de Archivo', size=128, readonly=True)
    file    = fields.Binary(string='Archivo Excel', readonly=True)
    
    
    def create_excel_file(self):
        filename = 'Integracion SBC para IMSS Periodo del ' + str(self.date_from) + ' al ' + str(self.date_to) + '.xlsx'
        
        bimestre = {1  : '1', 2  : '1',
                    3  : '2', 4  : '2',
                    5  : '3', 6  : '3',
                    7  : '4', 8  : '4',
                    9  : '5', 10 : '5',
                    11 : '6', 12 : '6',
                   }
        # Empezamos a generar documento en Excel
        tmp_file = NamedTemporaryFile()
        wb = xlsxwriter.Workbook(tmp_file)
        ws = wb.add_worksheet(filename)
        
        # Encabezado de la Hoja de Calculo
        
        company = self.env.user.company_id
        
        merge_format = wb.add_format({'align'    : 'center',
                                      'valign'   : 'vcenter',
                                      'bold'     : True,
                                      'text_wrap': True,
                                      'font_size': 12})

        ws.merge_range('A1:B4', ' ', merge_format)
        if company.logo:
            logo = BytesIO(base64.b64decode(company.logo_web))
            ws.insert_image('A1', 'logo.png', {'image_data': logo,
                                               'x_scale': 0.5, 
                                               'y_scale': 0.5,
                                               'x_offset': 100, 
                                               'y_offset': 1})
        
        ws.merge_range('C1:K1', company.name, merge_format)
        ws.merge_range('C2:K2', 'RFC: ' + (company.vat or '') + ' - Registro Patronal: ' + (company.registro_patronal or ''), merge_format)        
        ws.merge_range('C3:K3', 'Integración de Salarios Base de Cotización para efectos del I.M.S.S. e INFONAVIT', merge_format)
        ws.merge_range('C4:K4', '%s Bimestre %s  Del: %s al %s' % (self.contract_ids[0].sat_periodicidadpago_id.name, bimestre[self.date_to.month], self.date_from.strftime('%d/%m/%Y'), self.date_to.strftime('%d/%m/%Y')), merge_format)
        ws.merge_range('C5:K5', 'SBC fija + variable', merge_format)

        title_format = wb.add_format({'bold': True, 
                                      #'align' : 'center',
                                      'valign': 'vcenter', # vcentre
                                      'text_wrap': True,
                                      'font_size' : 10,
                                      'border'  : True,
                                      'bg_color' : '#DCDCDC',
                                     })

        title_format1 = wb.add_format({'bold': True, 
                                      'align' : 'center',
                                      'valign': 'vcenter', # vcentre
                                      'text_wrap': True,
                                      'font_size' : 10,
                                      'border'  : True,
                                      'bg_color' : '#DCDCDC',
                                     })
        
        title_format2 = wb.add_format({'bold': True, 
                                      'align' : 'center',
                                      'valign': 'vcenter', # vcentre
                                      'text_wrap': True,
                                      'font_size' : 10,
                                      'border'  : True,
                                      'bg_color' : '#A9D6E1',
                                     })
        title_format3 = wb.add_format({'bold': True, 
                                      'align' : 'center',
                                      'valign': 'vcenter', # vcentre
                                      'text_wrap': True,
                                      'font_size' : 10,
                                      'border'  : True,
                                      'bg_color' : '#D1F2FA',
                                     })
        title_format4 = wb.add_format({'bold': True, 
                                      'align' : 'center',
                                      'valign': 'vcenter', # vcentre
                                      'text_wrap': True,
                                      'font_size' : 10,
                                      'border'  : True,
                                      'bg_color' : '#FEC979',
                                     })
        
        # titulos de columnas
        ws.set_row(10, 25)
        ws.set_column('B:B', 35)
        ws.set_column('C:P', 12)
        ws.set_column('V:V', 15)
        ws.merge_range('A10:A11', 'Código', title_format1)
        ws.merge_range('B10:B11', 'Trabajador', title_format1)
        ws.merge_range('C10:C11', 'Fecha Alta o Reingreso', title_format1)
        ws.merge_range('D10:D11', 'Incapacitado a la  fecha de aplicación', title_format1)
        ws.merge_range('E10:E11', 'N.S.S.', title_format1)
        ws.merge_range('F10:F11', 'Tipo Prestación', title_format1)
        ws.merge_range('G10:G11', 'Base Cotización', title_format1)
        
        ws.merge_range('H10:L10', 'SBC ACTUAL', title_format2)
        ws.write('H11', 'Parte Fija', title_format2)
        ws.write('I11', 'Ultima Modificación', title_format2)
        ws.write('J11', 'Parte Variable', title_format2)
        ws.write('K11', 'Ultima Modificación', title_format2)
        ws.write('L11', 'SBC', title_format2)
        
        
        ws.merge_range('M10:U10', 'SBC NUEVO', title_format3)
        ws.write('M11', 'Parte Fija', title_format3)
        ws.write('N11', 'Percepciones Variables', title_format3)
        ws.write('O11', 'Días Periodo', title_format3)
        ws.write('P11', 'Faltas', title_format3)
        ws.write('Q11', 'Incapacidades', title_format3)
        ws.write('R11', 'Días Neto', title_format3)
        ws.write('S11', 'Parte Variable', title_format3)
        ws.write('T11', 'NUEVO SBC', title_format3)
        ws.write('U11', 'Fecha Aplicación', title_format3)
        ws.set_column('W:W', 50)
        ws.merge_range('V10:V11', 'Aplicar Modificación', title_format4)
        ws.merge_range('W10:W11', 'Observaciones', title_format4)
        
        # Fin Encabezado
        
        format_number = wb.add_format({'valign'  : 'vcenter',
                                       'num_format': '#,##0.00',
                                       'font_size': 10})
        format_string = wb.add_format({'valign'  : 'vcenter',
                                       'font_size': 10})
        format_string_center = wb.add_format({'align' : 'center',
                                              'valign': 'vcenter', # vcentre
                                              'text_wrap': True,
                                              'font_size': 10})
        
        format_date_center = wb.add_format({'align' : 'center',
                                            'num_format': 'dd/mm/yyyy',
                                            'valign': 'vcenter', # vcentre
                                            'text_wrap': True,
                                            'font_size': 10})
        
        x = 11
        for line in self.line_ids:
            column = []
            # ID
            column.append({'data' : line.employee_id.num_empleado or '', 'format': format_string_center})
            
            # Trabajador
            column.append({'data' : line.employee_id.name or '', 'format': format_string})
            
            #Fecha Ingreso
            column.append({'data' : line.fecha_alta, 'format': format_date_center})
            
            #Incapacidato en fecha de Aplicacion
            column.append({'data' : line.incapacitado_en_fecha_aplicacion and 'SI' or 'NO', 'format': format_string_center})
            
            #NSS
            column.append({'data' : line.employee_nss, 'format': format_string_center})
            
            #Tipo Prestacion
            column.append({'data' : line.contract_sindicalizado=='Si' and 'Sindicalizado' or 'Confianza', 'format': format_string_center})
            
            #Base Cotizacion
            column.append({'data' : tipo_salario[line.contract_tipo_salario], 'format': format_string_center})
            
            #SBC Actual - Parte Fija
            column.append({'data' : line.sbc_actual_parte_fija, 'format': format_number})
            
            #SBC Actual - Parte Fija - Ultima Modificacion
            column.append({'data' : line.sbc_actual_ultima_modif, 'format': format_date_center})
            
            #SBC Actual - Parte Variable
            column.append({'data' : line.sbc_actual_parte_variable, 'format': format_number})
            
            #SBC Actual - Parte Variable - Ultima Modificacion
            column.append({'data' : line.sbc_actual_ultima_modif2, 'format': format_date_center})
            
            #SBC Actual - SBC
            column.append({'data' : line.sbc_actual_sbc, 'format': format_number})
            
            
            #SBC Nuevo - Parte Fija
            column.append({'data' : line.sbc_nuevo_parte_fija, 'format': format_number})
                        
            # Suma Percepciones Variables
            column.append({'data' : line.total_percepciones_variables, 'format': format_number})
            
            # Dias Periodo
            column.append({'data' : line.dias_base, 'format': format_number})
            
            # Dias Faltas
            column.append({'data' : line.dias_ausencia, 'format': format_number})
            
            # Dias Incapacidades
            column.append({'data' : line.dias_incapacidad, 'format': format_number})
            
            # Dias Neto
            column.append({'data' : line.dias_base - line.dias_ausencia - line.dias_incapacidad, 'format': format_number})
            
        
            #SBC Nuevo - Parte Variable
            column.append({'data' : line.sbc_nuevo_parte_variable, 'format': format_number})
            
            #SBC Nuevo - SBC
            column.append({'data' : line.sbc_nuevo_sbc, 'format': format_number})

            #SBC Nuevo - Fecha Aplicacion
            column.append({'data' : line.sbc_nuevo_fecha_aplicacion, 'format': format_date_center})
            
            #Aplicar Modificacion
            column.append({'data' : line.aplicar_modificacion_sbc and 'SI' or 'NO', 'format': format_string_center})
            
            #Observaciones
            column.append({'data' : line.notes or '', 'format': format_string})
            
            y = 0
            for c in column:
                ws.write(x, y, c['data'], c['format'])
                y += 1

            x += 1
            
        
        ws.merge_range('A10:A11', 'Código', title_format1)
        ws.merge_range('A' + str(x+1) + ':W' + str(x+1), 'Total Empleados: %s' % len(self.line_ids.ids), title_format)
        
        wb.close()
        tmp_file.seek(0)
        stream = tmp_file.read()
        self.write({'filename'  : filename,
                    'file'      : base64.b64encode(stream)})
        
        return True
            
            
            
            
            
            
            
            