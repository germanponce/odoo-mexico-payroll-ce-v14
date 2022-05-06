# -*- encoding: utf-8 -*-
#

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import csv
import os.path
import base64

import odoo.tools as tools
import os

import logging
_logger = logging.getLogger(__name__)


class overall_config_wizard_sat_models_nomina(models.TransientModel):
    _name = 'overall.config.wizard.sat.models.nomina'
    _description ="Asistente para cargar los Catalogos del SAT para Nominas"

    load_data = fields.Boolean('Informacion Cargada')
    action_status = fields.Text('Notas de Carga de Datos')

    
    def _reopen_wizard(self):
        return { 'type'     : 'ir.actions.act_window',
                 'res_id'   : self.id,
                 'view_mode': 'form',
                 'view_type': 'form',
                 'res_model': 'overall.config.wizard.sat.models.nomina',
                 'target'   : 'new',
                 'name'     : 'Carga de Catalogos para la Nomina CFDI 3.3'}


    def _find_file_in_addons(self, directory, filename):
        """To use this method, specify a filename and the directory where it resides.
        Said directory must be at the first level for the modules folders."""
        addons_paths = tools.config['addons_path'].split(',')
        actual_module = directory.split('/')[0]
        if len(addons_paths) == 1:
            return os.path.join(addons_paths[0], directory, filename)
        for pth in addons_paths:
            for subdir in os.listdir(pth):
                if subdir == actual_module:
                    return os.path.join(pth, directory, filename)

        return False
    
    def process_catalogs(self):        
        status = "La Informacion se Cargo de Forma Correcta."

        list_csv_data = [
                'data/sat.nomina.origenrecurso.csv',
                'data/sat.nomina.tipodeduccion.csv',
                'data/sat.nomina.tipojornada.csv',
                'data/sat.nomina.tipopercepcion.csv',
                'data/sat.nomina.periodicidadpago.csv',
                'data/sat.nomina.tipohoraextra.csv',
                'data/sat.nomina.tiponomina.csv',
                'data/sat.nomina.tiporegimen.csv',
                'data/sat.nomina.tipocontrato.csv',
                'data/sat.nomina.tipoincapacidad.csv',
                'data/sat.nomina.tipootropago.csv',
                'data/sat.nomina.riesgopuesto.csv',
                'data/sat.nomina.tabla_vacaciones.csv'
            ]
        cr = self.env.cr
        module_name = "l10n_mx_payroll"
        mode = "update"
        kind = "data"
        noupdate = True
        report = ""
        
        for csv_file in list_csv_data:
            _logger.info('\n***** Cargando el Fichero: %s\n' % csv_file)
            target_file = self._find_file_in_addons('l10n_mx_payroll', csv_file)
            #tools.convert_file(cr, module_name, csv_file, {}, mode, noupdate, kind, report)
            tools.convert_file(cr, module_name, csv_file, False, mode, noupdate, kind, target_file)
            _logger.info('\n ***** Fichero Cargado *****\n')
        #except:
        #    status = "Se encontraron Errores en el Procesamiento.\nContacte a Argil Consulting admon@argil.mx"

        _logger.info('\n ***** Fin de la Carga de Datos *****\n')

        self.write({'action_status': status,'load_data':True})
        return self._reopen_wizard()
