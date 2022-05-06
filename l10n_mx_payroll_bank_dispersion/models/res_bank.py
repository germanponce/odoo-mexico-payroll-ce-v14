# -*- encoding: utf-8 -*-
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError

import logging
_logger = logging.getLogger(__name__)

"""
<?xml version="1.0"?>
<t t-name="l10n_mx_payroll_bank_dispersion.santander_batch_file"><t t-set="numero_emisora" t-value="'12345'"/>HNE<t t-esc="numero_emisora"/><t t-esc="o.date_payroll.strftime('%Y%m%d')"/>01<t t-esc="str(len(o.slip_ids.filtered(lambda _w: _w.state in ('draft','done')).ids)).zfill(6)"/><t t-esc="str(int(sum(o.slip_ids.mapped('neto_a_pagar'))*100.0)).zfill(15)" /><t t-esc="'0'*6" /><t t-esc="'0'*15" /><t t-esc="'0'*6" /><t t-esc="'0'*15" /><t t-esc="'0'*6" />0<t t-foreach="o.slip_ids" t-as="nom">
D<t t-esc="nom.date_payroll.strftime('%Y%m%d')" /><t t-esc="len(nom.employee_id.num_empleado) &lt;=10 and ('0'*(10 - len(nom.employee_id.num_empleado))) + nom.employee_id.num_empleado or nomina.employee_id.num_empleado[10:]" /><t t-esc="' '*80" /><t t-esc="str(int(nom.neto_a_pagar*100.0)).zfill(15)" />12301<t t-esc="nom.employee_id.bank_account_id and nom.employee_id.bank_account_id.acc_number.zfill(18) or ('0'*18)" />0 <t t-esc="'0'*8" /></t>
</t>
"""

class IrSequence(models.Model):
    _inherit = 'ir.sequence'
    
    
    def _create_date_range_per_day_seq(self, date):
        seq_date_range = self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date,
            'date_to': date,
            'sequence_id': self.id,
        })
        return seq_date_range
    
    
    def _next_4_payroll_batch_file(self):
        """ Returns the next number in the preferred sequence in all the ones given in self."""
        if not self.use_date_range:
            return self._next_do()
        # date mode
        dt = fields.Date.today()
        if self._context.get('ir_sequence_date'):
            dt = self._context.get('ir_sequence_date')
        seq_date = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '<=', dt), ('date_to', '>=', dt)], limit=1)
        if not seq_date:
            seq_date = self._create_date_range_per_day_seq(dt)
        return seq_date.with_context(ir_sequence_date_range=seq_date.date_from)._next()

class ResBank(models.Model):
    _inherit = 'res.bank'

    
    payroll_batch_file_id = fields.Many2one(
        'ir.ui.view',
        string='Definición Archivo Batch Nómina',
        help="Definición para contruir Archivo de Texto a subir "
             "al portal bancario para dispersión de Nómina.")
    
    payroll_batch_file_company_code  = fields.Char(string="Clave Emisora",
                                                  help="Número de Emisora que el Banco le asignó a la empresa")
    
    payroll_batch_file_name = fields.Char(string="Nombre de archivo",
                                         help="Defina como se genera el nombre del archivo a subir al portal del banco. "
                                              "Por ejemplo: N%(emisora)s%(consecutivo)s.txt")
        
    payroll_batch_file_seq = fields.Many2one('ir.sequence', string="Secuencia",
                                            help="Secuencia a usar en caso de que así lo solicite el banco")
    
    
    
    def get_payroll_filename(self, payslip_run_id=False):
        self.ensure_one()
        vals = {'emisora' : self.payroll_batch_file_company_code or '', 
                'consecutivo' : self.payroll_batch_file_seq._next_4_payroll_batch_file(),
                }
        if not self.payroll_batch_file_name:
            return payslip_run_id and (payslip_run_id.name.replace(' ','_').replace('"','').replace("'",'').replace('/','_') + '.txt') or 'archivo.txt'

        try:
            filename = self.payroll_batch_file_name % vals
        except:
            raise ValidationError(_('Advertencia!\n\nLa definición de los parámetros para generar el archivo batch no son correctos, por favor revise la definición'))
            
        return filename
                
            
    
    