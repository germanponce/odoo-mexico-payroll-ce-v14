# -*- encoding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import xlrd
import base64

import logging
_logger = logging.getLogger(__name__)


class HRPayslipExtraImport(models.TransientModel):
    _name = 'hr.payslip.extra.import'
    _description = "Asistente para Importar Extras de Nomina de un archivo XLS"
    
    archivo = fields.Binary(string="Archivo", required=True)
    archivo_filename = fields.Char(string="Nombre Archivo")
    errores = fields.Text(string="Errores")
    state = fields.Selection([('draft','A Procesar'),
                              ('done','Procesado')],
                             default='draft', required=True,
                             string="Estado")
    
    def _reopen_wizard(self, res_id):
        return {'type'      : 'ir.actions.act_window',
                'res_id'    : res_id,
                'view_mode' : 'form',
                'view_type' : 'form',
                'res_model' : 'hr.payslip.extra.import',
                'target'    : 'new',
                'name'      : 'Errores de importación'}
    
    def action_confirm(self):
        extra_obj = self.env['hr.payslip.extra']
        salary_rule_obj = self.env['hr.salary.rule']
        employee_obj = self.env['hr.employee']
        contract_obj = self.env['hr.contract']

        doc = xlrd.open_workbook(
            None,
            file_contents=base64.b64decode(self.archivo),
            on_demand=False
        )

        wb = doc.sheet_by_index(0)
        
        # Las columnas deben ser:
        # 0. Empleado
        # 1. Contrato
        # 2. Fecha
        # 3. Regla Salarial
        # 4. Cantidad
        # 5. Monto
        
        errores = ''
        extras = []
        for x in range(1, wb.nrows):
            error = ''
            #_logger.info("\n\nwb.cell_value(x, 0): %s\nwb.cell_value(x, 1): %s\nwb.cell_value(x, 2): %s\nwb.cell_value(x, 3): %s\nwb.cell_value(x, 4): %s\nwb.cell_value(x, 5): %s\n" % (wb.cell_value(x, 0), wb.cell_value(x, 1), wb.cell_value(x, 2), wb.cell_value(x, 3), wb.cell_value(x, 4), wb.cell_value(x, 5)))
            employee_id = employee_obj.search([('active','in',(True,False)),
                                               ('name','=',wb.cell_value(x, 0))], limit=1)
            if not employee_id:
                error += _("\nNo se encontró el Empleado '%s'") % wb.cell_value(x, 0)
            contract_id = contract_obj.search([('active','in',(True,False)),
                                               ('name','=',wb.cell_value(x, 1))], limit=1)
            if not employee_id:
                error += _("\nNo se encontró el Contrato '%s'") % wb.cell_value(x, 1)
            
            fecha = wb.cell_value(x, 2)
            if fecha:
                w = xlrd.xldate_as_tuple(fecha, 0)
                fecha = date(w[0], w[1], w[2])
                #_logger.info("fecha: %s" % fecha)
            else:
                error += _("\nLa fecha no está correcta '%s'") % wb.cell_value(x, 2)
            if not isinstance(fecha, date):
                error += _("\nLa fecha no está correcta '%s'") % wb.cell_value(x, 2)
                
            rule_id = salary_rule_obj.search([('name','=',wb.cell_value(x, 3))], limit=1)    
            if not rule_id:
                error += _("\nNo se encontró la Regla Salarial '%s'") % wb.cell_value(x, 3)
            
            cant = wb.cell_value(x, 4)
            if not isinstance(cant, float):
                error += _("\nLa cantidad no está correcta '%s'") % wb.cell_value(x, 4)
                
            monto = wb.cell_value(x, 5)
            if not isinstance(monto, float):
                error += _("\nEl monto no está correcta '%s'") % wb.cell_value(x, 5)
            
            _logger.info("error: %s" % error)
            if error:
                errores += error
            else:
                extras.append({
                    'employee_id' : employee_id.id,
                    'contract_id' : contract_id.id,
                    'date'        : fecha,
                    'hr_salary_rule_id' : rule_id.id,
                    'qty' : cant,
                    'amount' : monto,
                })
        
        self.state='done'
        if not errores:
            extra_ids = extra_obj.browse([])
            for x in extras:
                extra_ids += extra_obj.create(x)
            
            action = self.env.ref('l10n_mx_payroll.action_hr_payslip_extra').sudo()
            result = action.read()[0]
            result['domain'] = [('id', 'in', extra_ids.ids)]
            return result
        else:
            self.errores = errores
            return self._reopen_wizard(self.id)
