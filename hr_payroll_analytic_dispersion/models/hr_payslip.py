# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, date, timedelta
from odoo.tools import float_compare, float_is_zero
import base64
import logging
_logger = logging.getLogger(__name__)


class HRSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    aplicar_dispersion_analitica = fields.Boolean(string="Aplicar Dispersión Analítica",
                                                 help="Si activa entonces será tomado para hacer la dispersión Analítica.")
    

class HRPayslipRunAnalyticDispersion(models.TransientModel):
    _name = 'hr.payslip.run.analytic.dispersion'
    _description = 'Dispersion de Cuentas Contables de Acuerdo a archivo'
    
    archivo = fields.Binary(string="Archivo", required=True)
    archivo_filename = fields.Char(string="Nombre Archivo")
    payslip_run_id = fields.Many2one('hr.payslip.run', required=True)
    
    
    @api.model
    def default_get(self, fields):
        rec = super(HRPayslipRunAnalyticDispersion, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        # Check for selected hr.payslip.run
        if not active_ids or active_model != 'hr.payslip.run':
            return rec

        lista = self.env['hr.payslip.run'].browse(active_ids)
        rec.update({
            'payslip_run_id': lista[0].id,
        })
        return rec
    
    
    def action_process(self):
        empleados = {}
        archivo_x = str(base64.b64decode(self.archivo)).replace("'",'')
        try:
            lines = archivo_x.split("\\n")
        except:
            raise ValidationError(_("Advertencia!\nEl archivo que subió no cumple con los requerimientos de formato, por favor revise y re-intente la operación."))
        
        _logger.info("lines: %s" % lines)
        salary_rule_obj = self.env['hr.salary.rule']
        emp_obj = self.env['hr.employee']
        acc_obj = self.env['account.analytic.account']
        lines.pop(0) # Quitamos la linea de titulos
        cont = 1
        suma_porc = 100.0
        last_employee = 0
        last_employee_name = ''
        _logger.info("lines: %s" % lines)
        for line in lines:
            vals = line.split(",")
            _logger.info("vals: %s" % vals)
            if len(vals) != 3: # No tiene informacion
                raise ValidationError(_("Advertencia!\nError en la línea %s. Parece que falta algún valor.\n%s") % (cont, line))
            
            # Buscamos el empleado
            emp_id = emp_obj.search_read([('name','=ilike','%'+vals[0]+'%')], ['id','name'], limit=1)
            _logger.info("emp_id: %s" % emp_id)
            if not emp_id:
                raise ValidationError(_("Advertencia!\nError en la línea %s. Parece que el nombre del Empleado no existe.\n%s\nEmpleado: %s") % (cont, line, vals[0]))
            
            # Buscamos la cuenta analitica
            acc_id = acc_obj.search_read([('code','=ilike','%'+vals[2]+'%')], ['id'], limit=1)
            if not acc_id:
                raise ValidationError(_("Advertencia!\n\nError en la línea %s. \nParece que la cuenta analítica NO existe.\nCódigo Cuenta: %s\n%s") % (cont, vals[2], line))
            
            
            if emp_id[0]['id'] not in empleados:
                empleados[emp_id[0]['id']] = [{'porcentaje' : float(vals[1])/100.0, 'analitica' : acc_id[0]['id']}]
                if last_employee != 0 and not (99.999 < suma_porc < 100.001): # Checamos si la suma del porcentaje del empleado anterior es 100.00
                    raise ValidationError(_("Advertencia!\nLa suma del porcentaje para el Empleado %s - %s no es 100.0. Por favor revise") % (last_employee, last_employee_name))
                suma_porc = float(vals[1])
                last_employee = emp_id[0]['id']
                last_employee_name = emp_id[0]['name']
            else:
                empleados[emp_id[0]['id']].append({'porcentaje' : float(vals[1])/100.0, 'analitica' : acc_id[0]['id']})
                suma_porc += float(vals[1])
            
        if not (99.999 < suma_porc < 100.001): # Checamos si la suma del porcentaje del ultimo empleado es 100.00
            raise ValidationError(_("Advertencia!\nLa suma del porcentaje para el Empleado %s - %s no es 100.0. Por favor revise") % (last_employee, last_employee_name))
        
        _logger.info("empleados: %s" % empleados)

        warning = {
                'title': _("Notificación"),
                'message': _("No se encontró ninguna nómina para hacer la Distribución Analítica.")
            }     
        aml_obj = self.env['account.move.line']
        for slip in self.payslip_run_id.slip_ids.filtered(lambda w: w.state=='done'):
            if slip.employee_id.id not in empleados:
                continue
            _logger.info("\n========== Procesando: %s ==========\n" % slip.number)
            dispersion = empleados[slip.employee_id.id]
            slip.move_id.button_cancel()
            move_lines = aml_obj.browse([])
            for move_line in slip.move_id.line_ids:
                # Buscar regla
                regla = salary_rule_obj.search([('name','=',move_line.name)],limit=1)
                if not regla or not regla.aplicar_dispersion_analitica:
                    _logger.info("Regla %s - %s no se dispersa" % (regla.code, regla.name))
                    continue
                # Revisar si se debe dispersar
                move_lines += move_line
                debit, credit = move_line.debit, move_line.credit
                line = move_line.copy_data()[0]
                _logger.info("\n- - - - - - - - - - - - - - - - -")
                _logger.info("\n\ndebit: %s ** credit: %s\n" % (debit, credit))
                x = len(dispersion)
                for d in dispersion:
                    _logger.info("\n./\./\./\./\./\./\./\nd: %s" % d)
                    line['analytic_account_id'] = d['analitica']
                    if debit:
                        line['debit'] = round(d['porcentaje'] * move_line.debit, 2)
                        debit -= line['debit']
                    elif credit:
                        line['credit'] = round(d['porcentaje'] * move_line.credit, 2)
                        credit -= line['credit']
                    _logger.info("\nline['debit']: %s ** line['credit']: %s" % (line['debit'], line['credit']))
                    _logger.info("\n\ndebit: %s ** credit: %s\n" % (debit, credit))
                    if x == 1:
                        if round(debit, 2):
                            line['debit'] += round(debit, 2)
                        if round(credit, 2):
                            line['credit'] += round(credit, 2)

                    _logger.info("\n\ndebit: %s ** credit: %s\n" % (debit, credit))
                    _logger.info("\n*********\nline: %s" % line)
                    xline = aml_obj.with_context(check_move_validity=False).create(line)
                    _logger.info("xline: %s" % xline)
                    x -= 1
            _logger.info("move_lines: %s" % move_lines)
            if move_lines:
                move_lines.with_context(check_move_validity=False).unlink()
            slip.move_id.post()
            warning = {
                'title': _("Notificación"),
                'message': _("Se procesaron las nóminas de esta Lista de Nóminas, por favor revise el resultado.")
            }
            
        return {'warning': warning}
                
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:    
