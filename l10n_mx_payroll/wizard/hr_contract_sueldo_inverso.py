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

dias = {'mensual' : 30.4,
        'quincenal': 15.2,
        'semanal' : 7.0 }

class HRContractSueldoInverso(models.TransientModel):
    _name = 'hr.contract.sueldo_inverso'
    _description = "Wizard para obtener Calculo inverso"
    
    #name = fields.Char(string="Nombre", required=False)
    tipo_sueldo = fields.Selection(
        [('bruto', 'Sueldo Bruto'),
         ('neto', 'Sueldo Neto'),
        ], string="Tipo Cálculo", default='bruto', required=True)
    
    periodo = fields.Selection(
        [('mensual', 'Mensual (30.4 días)'),
         ('quincenal', 'Quincenal (15.2 días)'),
         ('semanal', 'Semanal (7 días)'),
        ], string="Periodo", default='mensual', required=True)
    
    sindicalizado = fields.Selection(
        [('Si','Sindicalizado'),
         ('No','De Confianza')],
        string="Tipo Empleado", default='No', required=True)
    
    dias_aguinaldo = fields.Integer(string="Días Aguinaldo", default=0, required=True)
    dias_vacaciones = fields.Integer(string="Días Vacaciones", default=0, required=True)
    porc_prima_vacacional = fields.Float(string="% Prima Vacacional", default=0, required=True)
    monto_base = fields.Float(string="Monto Base", digits=(16,2), default=0, required=True)
    sueldo_bruto = fields.Float(string="Sueldo Bruto", digits=(16,4), default=0)
    monto_isr_base          = fields.Float(string=">>ISR antes de Subsidio", digits=(16,2), default=0)
    monto_subsidio_causado    = fields.Float(string=">>Subsidio Causado", digits=(16,2), default=0)
    monto_isr          = fields.Float(string="ISR", digits=(16,2), default=0)
    monto_subsidio_entregado    = fields.Float(string="Subsidio al Empleo", digits=(16,2), default=0)
    
    monto_imss   = fields.Float(string="IMSS", digits=(16,2), default=0)
    sueldo_neto  = fields.Float(string="Sueldo Neto", digits=(16,2),default=0)
    
    salario_minimo = fields.Float(string="Salario Mínimo", digits=(16,2),default=0)
    uma            = fields.Float(string="UMA", digits=(16,2), default=0)
    sueldo_diario  = fields.Float(string="Sueldo Diario", digits=(16,4), default=0)
    sueldo_sbc     = fields.Float(string="SBC", digits=(16,4), default=0)
    
    tabla_isr = fields.Many2many('sat.nomina.tabla_isr', string="Tabla ISR")
    
    tabla_subsidio = fields.Many2many('sat.nomina.tabla_subsidio', 
                                      string="Tabla Subsidio al Empleo")
    
    @api.model
    def default_get(self, default_fields):
        res = super(HRContractSueldoInverso, self).default_get(default_fields)
        salario_minimo = self.env['sat.nomina.salario_minimo'].search([('tipo','=','smg')], 
                                                                      order='vigencia desc', limit=1)
        
        uma = self.env['sat.nomina.uma_umi'].search([('tipo','=','uma')],
                                                    order='vigencia desc', limit=1)
        
        tabla_isr, tabla_subsidio = self.get_tablas()
        
        res.update({'salario_minimo' : salario_minimo and salario_minimo.monto or 0,
                    'uma' : uma and uma.monto or 0,
                    'tabla_isr' : tabla_isr.ids,
                    'tabla_subsidio' : tabla_subsidio.ids,
                   })
        return res
    
    
    def get_max_date(self, vigencias):
        if not vigencias:
            return fields.Date.today()
        fechas = []
        for _w in vigencias:
            if _w.vigencia not in fechas:
                fechas.append(_w.vigencia)
        return max(fechas) # asumimos tipo de dato "date"
    
    def get_tablas(self):
        tabla_isr_obj = self.env['sat.nomina.tabla_isr']
        tabla_subs_obj = self.env['sat.nomina.tabla_subsidio']
        vigencias = tabla_isr_obj.search([("vigencia", "<=", fields.Date.today()),
                                          ('tipo','=','mensual')])
        tabla_isr = tabla_isr_obj.search([('vigencia','=',self.get_max_date(vigencias)),
                                      ('tipo','=','mensual')])
        vigencias = tabla_subs_obj.search([("vigencia", "<=", fields.Date.today()),
                                           ('tipo','=','mensual')])
        tabla_subsidio = tabla_subs_obj.search([('vigencia','=',self.get_max_date(vigencias)),
                                                ('tipo','=','mensual')])
        return tabla_isr, tabla_subsidio
    
    
    def calcular(self, monto_base):
        self.sueldo_bruto = monto_base
        self.sueldo_diario = self.sueldo_bruto / dias[self.periodo]

        # Calcular el factor de integracion
        monto_aguinaldo = self.dias_aguinaldo * self.sueldo_diario
        monto_prima_vacacional = self.sueldo_diario * self.dias_vacaciones * self.porc_prima_vacacional / 100.0
        factor = ((self.sueldo_diario * 365.0) + monto_aguinaldo + monto_prima_vacacional) / (self.sueldo_diario * 365.0)
        self.sueldo_sbc = self.sueldo_diario * factor

        # Calculo del ISR
        gravada_promedio_mensual = self.sueldo_diario * 30.4
        monto_isr, monto_subsidio = 0.0, 0.0

        for line in self.tabla_isr.filtered(lambda w: w.limite_inferior <= gravada_promedio_mensual <= w.limite_superior):
            excedente = gravada_promedio_mensual - line.limite_inferior
            impuesto_marginal = excedente * (line.tasa / 100.0)
            monto_isr = ((impuesto_marginal + line.cuota_fija) / 30.4) * dias[self.periodo]

        for line in self.tabla_subsidio.filtered(lambda w: w.limite_inferior <= gravada_promedio_mensual <= w.limite_superior):
            monto_subsidio = line.subsidio / 30.4 * dias[self.periodo]

        self.monto_isr_base = monto_isr
        self.monto_subsidio_causado = monto_subsidio
        if monto_isr > monto_subsidio:
            self.monto_isr = monto_isr - monto_subsidio
            self.monto_subsidio_entregado = 0
        else:
            self.monto_isr = 0
            self.monto_subsidio_entregado = monto_subsidio - monto_isr


        # Calculo del IMSS
        tope_tres_salarios_minimos = self.uma * 3.0
        percepciones = self.sueldo_sbc * dias[self.periodo]
        if (tope_tres_salarios_minimos * dias[self.periodo]) > percepciones:
            enf_y_mat_excedente = 0.0
        else:
            enf_y_mat_excedente = (percepciones - (tope_tres_salarios_minimos * dias[self.periodo])) * 0.004
        enf_y_mat_prest_dinero = percepciones * 0.0025
        enf_y_mat_pens_y_benef =  percepciones  * 0.00375
        invalidez_y_vida = percepciones * 0.00625
        cesantia_y_vejez = percepciones * 0.01125

        self.monto_imss = enf_y_mat_excedente + enf_y_mat_prest_dinero + enf_y_mat_pens_y_benef + invalidez_y_vida + cesantia_y_vejez


        self.sueldo_neto = self.sueldo_bruto - \
                            self.monto_isr + \
                            self.monto_subsidio_entregado - \
                            self.monto_imss
    
    @api.onchange('monto_base','tipo_sueldo', 'periodo', 'sindicalizado')
    def get_data(self):
        # Validaciones
        if not self.monto_base or self.monto_base < 0:
            return
            raise ValidationError(_("No ha definido el Monto sobre el cual hacer los cálculos"))
        
        prest_line = self.env['sat.nomina.tabla_prestaciones'].search(
            [('antiguedad','=',0),
             ('sindicalizado','=',self.sindicalizado)], 
            limit=1)
        if prest_line:
            self.dias_vacaciones = prest_line.dias_vacaciones
            self.porc_prima_vacacional = prest_line.prima_vacacional
            self.dias_aguinaldo  = prest_line.dias_aguinaldo
        else:
            self.dias_vacaciones = 6.0
            self.dias_aguinaldo  = 15.0
            self.porc_prima_vacacional = 25.0
        
        
        self.calcular(self.monto_base)
        if self.tipo_sueldo=='bruto':
            return
        
        # Continuamos con Calculo del Neto
        ################################
        monto_base = self.monto_base
        monto = self.monto_base
        monto_objetivo = self.monto_base
        monto_actual = self.sueldo_neto
        porcentaje = 0.2
        factor = 0.1
        last_update = True
        cont = 0
        while not ((monto_objetivo + 0.01) > monto_actual > (monto_objetivo - 0.01)) and cont < 35:
            cont += 1
            _logger.info("= = = = = = = = = = =")
            _logger.info("==== Intento: %s ====" % cont)
            _logger.info("porcentaje anterior: %s" % porcentaje)
            _logger.info("monto_objetivo: %s" % monto_objetivo)
            _logger.info("monto_actual: %s" % monto_actual)
            if (monto_objetivo - 0.01) > monto_actual:
                if not last_update:
                    _logger.info("factor: %s" % factor)
                    last_update = True
                    factor = 0.05 if factor==0.1 else (0.01 if factor==0.05 else (0.005 if factor==0.01 else (0.001 if factor==0.005 else (0.0005 if factor==0.001 else (0.0001 if factor==0.0005 else (0.00005 if factor==0.0001 else (0.00001 if factor==0.00005 else (0.000005 if factor==0.00001 else (0.000001 if factor==0.000005 else (0.0000005 if factor==0.000001 else (0.0000001 if factor==0.0000005 else 0.00000001)))))))))))
                    _logger.info("factor: %s" % factor)
                porcentaje += factor
                _logger.info("aumenta porcentaje: %s" % porcentaje)
            elif (monto_objetivo + 0.01) < monto_actual:
                if last_update:
                    _logger.info("factor: %s" % factor)
                    last_update = False
                    factor = 0.05 if factor==0.1 else (0.01 if factor==0.05 else (0.005 if factor==0.01 else (0.001 if factor==0.005 else (0.0005 if factor==0.001 else (0.0001 if factor==0.0005 else (0.00005 if factor==0.0001 else (0.00001 if factor==0.00005 else (0.000005 if factor==0.00001 else (0.000001 if factor==0.000005 else (0.0000005 if factor==0.000001 else (0.0000001 if factor==0.0000005 else 0.00000001)))))))))))
                    _logger.info("factor: %s" % factor)
                porcentaje -= factor
                _logger.info("disminuye porcentaje: %s" % porcentaje)
            else:
                break
            
            monto = round(monto_base * (1.0 + porcentaje), 2)
            self.calcular(monto)
            monto_actual = self.sueldo_neto
        
            _logger.info("monto_actual: %s" % monto_actual)
            _logger.info("monto_objetivo: %s" % monto_objetivo)
            _logger.info("==== Intento: %s ====" % cont)
            if round(monto_actual - 0.01, 2) == round(monto_objetivo, 2):
                monto = round(monto - 0.01, 2)
                self.calcular(monto)
            elif round(monto_actual + 0.01, 2) == round(monto_objetivo, 2):
                monto = round(monto + 0.01, 2)
        ################################
        
            
            
        
        
        
    
    