# -*- encoding: utf-8 -*-
#

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import csv
import os.path
import base64

import odoo.tools as tools

import logging
_logger = logging.getLogger(__name__)


class SAT_CatalogosWizardPayroll(models.TransientModel):
    _name = 'sat.catalogos.wizard.payroll'
    _description = "Wizard para abrir un catalogo en particular del SAT"

    catalogo = fields.Selection([('origenrecurso',  'Origen Recurso'),
                                 ('tipodeduccion',  'Deducciones'),
                                 ('tipojornada',    'Jornada Laboral'),
                                 ('tipopercepcion', 'Percepciones'),
                                 ('periodicidadpago', 'Periodicidad de Pago'),
                                 ('tipohoraextra',  'Horas Extras'),
                                 ('tiponomina',     'Nóminas'),
                                 ('tiporegimen',    'Regímenes Laborales'),
                                 ('tipocontrato', 'Contratos'),
                                 ('tipoincapacidad', 'Incapacidades'),
                                 ('tipootropago', 'Otros Pagos'),
                                 ('riesgopuesto', 'Riesgos'),
                                ],
                               string="Catálogo a revisar", required=True)
    

    
    def open_catalog(self):
        data = {'origenrecurso' :   'c_OrigenRecurso',
                'tipodeduccion' :   'c_TipoDeduccion',
                'tipojornada'   :   'c_TipoJornada',
                'tipopercepcion':   'c_TipoPercepcion',
                'periodicidadpago': 'c_PeriodicidadPago',
                'tipohoraextra' :   'c_TipoHoras',
                'tiponomina'    :   'c_TipoNomina',
                'tiporegimen'   :   'c_TipoRegimen',
                'tipocontrato'  :   'c_TipoContrato',
                'tipoincapacidad':  'c_TipoIncapacidad',
                'tipootropago'  :   'c_TipoOtroPago',
                'riesgopuesto'  :   'c_RiesgoPuesto',
               }
        
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('l10n_mx_payroll.action_sat_' + data[self.catalogo])
        list_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.sat_' + data[self.catalogo] + '_tree')
        form_view_id = imd.xmlid_to_res_id('l10n_mx_payroll.sat_' + data[self.catalogo] + '_form')

        return {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
