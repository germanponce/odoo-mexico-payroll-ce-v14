# coding: utf-8

from odoo import api, tools, SUPERUSER_ID
#from os.path import join, dirname, realpath
import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    _logger.info("l10n_mx_payroll - Cargando Catálogos SAT")
    
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

    module_name = "l10n_mx_payroll"
    mode = "update"
    kind = "data"
    noupdate = True
    report = ""

    for csv_file in list_csv_data:        
        tools.convert_file(cr, module_name, csv_file, {}, mode=mode, noupdate=noupdate) #, kind, report)
        _logger.info('\n ***** Fichero Cargado *****\n')
        
    _logger.info("l10n_mx_payroll - Fin de Carga Catálogos SAT")
