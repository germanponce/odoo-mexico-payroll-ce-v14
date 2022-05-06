# -*- encoding: utf-8 -*-
##############################################################################

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression

import logging
_logger = logging.getLogger(__name__)



##### Tabla Causas de Terminación de Relación Laboral
class HRPayroll_CausaTerminacionRelacionLaboral(models.Model):
    _name = 'hr.causa_fin_relacion_laboral'
    _description = 'Causas de Terminacion de Relacion Laboral'

    code = fields.Char('Código', required=True)
    name = fields.Char('Causa supuesta', required=True)
    
    indemnizacion_90_dias = fields.Boolean(string="Indemnización (90 días)")
    indemnizacion_20_dias = fields.Boolean(string="Indemnización (20 días x año)")
    prima_antiguedad_12_dias = fields.Boolean(string="Prima Antigüedad (12 días x año)")
    prima_antiguedad_15_anios = fields.Boolean(string="Prima de Antigüedad (Antig. >= 15 años)")
    gratif_x_invalidez = fields.Boolean(string="Gratificación por Invalidez")
    salarios_vencidos = fields.Boolean(string="Salarios Vencidos")
    type        = fields.Selection([('finiquito','Finiquito'),
                                    ('liquidacion','Liquidación')],
                                  string="Tipo", required=True, default='finiquito')
    active = fields.Boolean(string="Activo", default="True")

    _sql_constraints = [
        ('name_unique', 'unique(name)','El registro debe ser único'),
        ('code_unique', 'unique(code)','El registro debe ser único')]
    
        
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    

######### CARGA DE CATALOGOS DEL SAT PARA NOMINAS ############

##### Tabla Factores IMSS
class HRPayroll_TablaFactoresIMSS(models.Model):
    _name = 'sat.nomina.factores_imss'
    _description = 'SAT - Primas por ramo de Seguro.'
    _order = "vigencia"

    
    @api.depends('vigencia', 'tipo_seguro', 'prestacion', 'tipo_cuota')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia and rec.tipo_seguro and rec.prestacion:
                rec.name = dict(rec._fields['tipo_seguro'].selection).get(rec.tipo_seguro) + ' - ' + \
                           dict(rec._fields['prestacion'].selection).get(rec.prestacion) + ' - ' + \
                           ((rec.tipo_seguro == 'enfermedades_y_maternidad' and rec.prestacion == 'en_espacio') and \
                            (dict(rec._fields['tipo_cuota'].selection).get(rec.tipo_cuota) + ' - ')  or '') + \
                            _(' Vigente desde: ') + rec.vigencia.strftime('%Y-%m-%d')
            else:
                rec.name = '/'

                
    @api.depends('cuota_trabajador', 'cuota_patron')
    def _compute_cuota(self):
        for rec in self:
            rec.cuota_total = rec.cuota_trabajador + rec.cuota_patron
            
            
                
    name = fields.Char('Prima', store=True, compute='_compute_name')
    sequence = fields.Integer(default=10)
    
    tipo_seguro      = fields.Selection([('riesgo_de_trabajo','Riesgo de Trabajo'),
                                         ('enfermedades_y_maternidad','Enfermedades y Maternidad'),
                                         ('invalidez_y_vida','Invalidez y Vida'),
                                         ('ceav','Retiro, Cesantía en Edad Avanzada y Vejez (CEAV)'),
                                         ('prestaciones_sociales','Guarderías y Prestaciones Sociales'),
                                         ('invalidez_y_vida','Invalidez y Vida'),],
                                      string="Tipo Prima de Seguro", required=True)
    
    prestacion      = fields.Selection([('en_especie_y_dinero','En Especie y Dinero'),
                                         ('en_especie','En Especie'),
                                         ('en_dinero','En Dinero'),
                                         ('gastos_medicos','Gastos médicos para pensionados y beneficiarios'),
                                         ('retiro','Retiro'),
                                         ('ceav','CEAV'),],
                                      string="Tipo Prestación", required=True)
    
    tipo_cuota      = fields.Selection([('fija','Cuota Fija'),
                                        ('adicional','Cuota Adicional')],
                                      string="Tipo Cuota", required=True,
                                      help="Aplica solo para Tipo Prima: Enfermedades y Maternidad - Tipo Prestación: En Especie",
                                       default="fija")
    
    cuota_patron        = fields.Float('Cuota Patrón %', digits=(18,3), required=True, default=0.0)
    cuota_trabajador    = fields.Float('Cuota Trabajador %', digits=(18,3), required=True, default=0.0)
    cuota_total         = fields.Float('Cuota Total %', digits=(18,3), compute="_compute_cuota")
    
    base_calculo_patron = fields.Char(string="Base Cálculo Patrón")
    base_calculo_trabajador = fields.Selection([('uma','UMA'),
                                                ('sbc', 'Salario Base de Cotización'),
                                                ('diff_sbc_3_uma' , 'Diferencia entre el SBC y tres veces la UMA')],
                                              string="Base Cálculo Trabajador", required=True)
    
    vigencia        = fields.Date('Vigencia', required=True)

    _sql_constraints = [
        ('vigencia_unique', 'unique(name,tipo_cuota)','El registro debe ser único')]


##### Tabla Salario Minimo
class HRPayroll_TablaSalarioMinimo(models.Model):
    _name = 'sat.nomina.salario_minimo'
    _description = 'SAT - Salario Mínimo.'
    _order = "vigencia"

    
    @api.depends('tipo','vigencia', 'monto')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia and rec.monto:
                rec.name =  (_('SM - ') if rec.tipo=='smg' else _('SMFN - '))  + str(rec.monto) + _(' - Desde: ') + rec.vigencia.strftime('%Y-%m-%d')
            else:
                rec.name = '/'
                
    name = fields.Char('Descripción', store=True, compute='_compute_name')
    tipo        = fields.Selection([('smg', 'Salario Mínimo General'),
                                    ('smfn', 'Salario Mínimo Frontera Norte'),
                                   ], string="Tipo", required=True, default='smg')
    monto            = fields.Float('Monto', digits=(18,2), required=True)
    vigencia        = fields.Date('Vigencia', required=True)

    _sql_constraints = [
        ('vigencia_unique', 'unique(tipo, vigencia)','La vigencia debe ser única')]



##### Tabla UMA
class HRPayroll_Tabla_UMA_UMI(models.Model):
    _name = 'sat.nomina.uma_umi'
    _description = 'SAT - UMA y UMI'
    _order = "vigencia"

    @api.depends('tipo','vigencia', 'monto')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia and rec.monto:
                rec.name = ('UMA - ' if rec.tipo=='uma' else 'UMI - ') + str(rec.monto) + _(' - Desde: ') + rec.vigencia.strftime('%Y-%m-%d')
            else:
                rec.name = '/'
                
    name        = fields.Char('Descripción', store=True, compute='_compute_name')
    tipo        = fields.Selection([('uma', 'UMA'),
                                    ('umi', 'UMI'),
                                   ], string="Tipo", required=True)
    monto       = fields.Float('Monto', digits=(18,2), required=True)
    vigencia    = fields.Date('Vigencia', required=True)
    
    
    _sql_constraints = [
        ('vigencia_unique', 'unique(tipo, vigencia)','El Tipo y la Vigencia deben ser únicos')]
    
##### Tabla Art 113 LISR
class HRPayroll_TablaISR(models.Model):
    _name = 'sat.nomina.tabla_isr'
    _description = 'SAT - Tabla Art. 113 Ley ISR.'
    _order = "sequence, tipo, vigencia, limite_inferior"
    
    @api.depends('tipo')
    def _compute_seq(self):
        seq = {'diaria'     : 10,
               'semanal'    : 20,
               'decenal'    : 30,
               'quincenal'  : 40,
               'mensual'    : 50,
               'anual'      : 60,
              }
        for rec in self:
            rec.sequence = seq[rec.tipo]
    
    @api.depends('tipo','vigencia', 'limite_inferior', 'limite_superior')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia and rec.limite_inferior and rec.limite_superior:
                val = dict(rec.fields_get(allfields=['tipo'])['tipo']['selection'])[rec.tipo]
                rec.name = 'Para Nómina: ' + val + ' - ' + rec.vigencia.strftime('%Y-%m-%d') + _(' - Límite Inf: ') + str(rec.limite_inferior) + _(' - Límite Sup: ') + str(rec.limite_superior)
            else:
                rec.name = '/'
    
    name = fields.Char('Descripción', store=True, compute='_compute_name')
    limite_inferior = fields.Float('Límite Inferior', digits=(18,2), required=True, index=True)
    limite_superior = fields.Float('Límite Superior', digits=(18,2), required=True, index=True)
    cuota_fija      = fields.Float('Cuota Fija', digits=(18,2), required=True)
    tasa            = fields.Float('Tasa (%)', digits=(18,2), required=True)
    vigencia        = fields.Date('Vigencia', required=True)
    tipo            = fields.Selection([('diaria', ' Diaria'),
                                        ('semanal', '  Semanal'),
                                        ('decenal', '   Decenal'),
                                        ('quincenal', '  Quincenal'),
                                        ('mensual', ' Mensual'),
                                        ('anual', '   Anual'),
                                       ], string="Aplica a Nómina", default='quincenal', required=True)
    sequence        = fields.Integer(string="Sec", compute="_compute_seq", store=True)
    
##### Tabla Subsidio al Empleo
class HRPayroll_TablaSubsidioEmpleo(models.Model):
    _name = 'sat.nomina.tabla_subsidio'
    _description = 'SAT - Tabla Subsidio al Empleo.'
    _order = "sequence, tipo, vigencia, limite_inferior"
    
    @api.depends('tipo')
    def _compute_seq(self):
        seq = {'diaria'     : 10,
               'semanal'    : 20,
               'decenal'    : 30,
               'quincenal'  : 40,
               'mensual'    : 50,
               'anual'      : 60,
              }
        for rec in self:
            rec.sequence = seq[rec.tipo]
    
    @api.depends('vigencia', 'limite_inferior', 'limite_superior')
    def _compute_name(self):
        for rec in self:
            if rec.vigencia and rec.limite_inferior and rec.limite_superior:
                val = dict(rec.fields_get(allfields=['tipo'])['tipo']['selection'])[rec.tipo]
                rec.name = 'Para Nómina: ' + val + ' - ' +  rec.vigencia.strftime('%Y-%m-%d') + _(' - Límite Inf: ') + str(rec.limite_inferior) + _(' - Límite Sup: ') + str(rec.limite_superior)
            else:
                rec.name = '/'
    
    name = fields.Char('Descripción', store=True, compute='_compute_name')
    limite_inferior = fields.Float('Límite Inferior', digits=(18,2), required=True, index=True)
    limite_superior = fields.Float('Límite Superior', digits=(18,2), required=True, index=True)
    subsidio        = fields.Float('Subsidio', digits=(18,2), required=True)
    vigencia        = fields.Date('Vigencia', required=True)
    tipo            = fields.Selection([('diaria', 'Diaria'),
                                        ('semanal', 'Semanal'),
                                        ('decenal', 'Decenal'),
                                        ('quincenal', 'Quincenal'),
                                        ('mensual', 'Mensual'),
                                        ('anual', 'Anual'),
                                       ], string="Aplica a Nómina", default='quincenal', required=True)
    sequence        = fields.Integer(string="Sec", compute='_compute_seq', store=True)
    
##### Tabla para Dias de Vacaciones
class HRPayroll_TablaVacaciones(models.Model):
    _name = 'sat.nomina.tabla_vacaciones'
    _description = 'SAT - Tabla para Dias de Vacaciones.'

    @api.depends('antiguedad')
    def _compute_name(self):
        for rec in self:
            if rec.antiguedad:
                rec.name = _('Antigüedad:') + str(rec.antiguedad)
            else:
                rec.name = '/'
    
    name = fields.Char('Descripción', store=True, compute='_compute_name')
    antiguedad  = fields.Integer('Antigüedad', required=True, index=True)
    dias        = fields.Integer('Días', required=True)
    
    
    

###### c_OrigenRecurso #########

class HRPayroll_c_OrigenRecurso(models.Model):
    _name = 'sat.nomina.origenrecurso'
    _description = 'SAT - Catálogo del tipo de origen recurso.'
    _order = 'code'

    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
###### c_PeriodicidadPago #########    
class HRPayroll_c_PeriodicidadPago(models.Model):
    _name = "sat.nomina.periodicidadpago"
    _description = 'SAT - Catálogo de tipos de periodicidad del pago.'
    _order = 'code'
    
    code = fields.Char(string="Código", size=8, required=True, index=True)
    name = fields.Text(string="Descripción", required=True, index=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")
    dias = fields.Float(string="Días", digits=(6,1), default=0.0)
    
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El Código debe ser único')]
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
###### c_TipoContrato #########
class HRPayroll_c_TipoContrato(models.Model):
    _name = 'sat.nomina.tipocontrato'
    _description = 'SAT - Catálogo de tipos de contrato.'
    _order = 'code'
    
    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
###### c_TipoDeduccion #########    
class HRPayroll_c_TipoDeduccion(models.Model):
    _name = "sat.nomina.tipodeduccion"
    _description = 'SAT - Catálogo de tipos de deducciones.'
    _order = 'code'
    
    code = fields.Char(string="Código", size=8, required=True, index=True)
    name = fields.Text(string="Descripción", required=True, index=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")
    
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El Código debe ser único')]
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
###### c_TipoHoras #########
class HRPayroll_c_TipoHoras(models.Model):
    _name = 'sat.nomina.tipohoraextra'
    _description = 'SAT - Catálogo de tipos de Horas Extra.'
    _order = 'code'
    
    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    
###### c_TipoIncapacidad #########
class HRPayroll_c_TipoIncapacidad(models.Model):
    _name = 'sat.nomina.tipoincapacidad'
    _description = 'SAT - Catálogo de tipos de Incapacidad.'
    _order = 'code'
    
    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)


###### c_TipoJornada #########
class HRPayroll_c_TipoJornada(models.Model):
    _name = 'sat.nomina.tipojornada'
    _description = 'SAT - Catálogo de tipos de Jornada Laboral.'
    _order = 'code'

    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    
###### c_TipoNomina #########
class HRPayroll_c_TipoNomina(models.Model):
    _name = 'sat.nomina.tiponomina'
    _description = 'SAT - Catálogo de tipos de Nómina.'
    _order = 'code'

    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    

###### c_TipoOtroPago #########
class HRPayroll_c_TipoOtroPago(models.Model):
    _name = 'sat.nomina.tipootropago'
    _description = 'SAT - Catálogo de Otros tipos de Pago.'
    _order = 'code'

    code = fields.Char('Código', required=True)
    name = fields.Char('Descripción', required=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")

    _sql_constraints = [
        ('code_unique', 'unique(code)','El Código debe ser único')]    

    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    

###### c_TipoPercepcion #########    
class HRPayroll_c_TipoPercepcion(models.Model):
    _name = "sat.nomina.tipopercepcion"
    _description = 'SAT - Catálogo de tipos de percepciones.'
    _order = 'code'
    
    code = fields.Char(string="Código", size=8, required=True, index=True)
    name = fields.Text(string="Descripción", required=True, index=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")
    
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El Código debe ser único')]
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    

###### c_TipoRegimen #########    
class HRPayroll_c_TipoRegimen(models.Model):
    _name = "sat.nomina.tiporegimen"
    _description = 'Catálogo de tipos de régimen de contratación.'
    _order = 'code'
    
    code = fields.Char(string="Código", size=8, required=True, index=True)
    name = fields.Text(string="Descripción", required=True, index=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")
    
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El Código debe ser único')]
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
###### c_RiesgoPuesto #########    
class HRPayroll_c_RiesgoPuesto(models.Model):
    _name = "sat.nomina.riesgopuesto"
    _description = 'Catálogo de clases en que deben inscribirse los patrones.'
    _order = 'code'
    
    code = fields.Char(string="Código", size=8, required=True, index=True)
    name = fields.Text(string="Descripción", required=True, index=True)
    vigencia_inicio = fields.Date(string="Vigencia Inicio", required=True)
    vigencia_fin    = fields.Date(string="Vigencia Fin")
    prima            = fields.Float('Prima de Riesgo de Trabajo (%)', digits=(18,6), required=True, default=0)
    
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El Código debe ser único')]
    
    
    def name_get(self):
        result = []
        for rec in self:
            name = "["+(rec.code or '')+"] "+(rec.name or '')
            result.append((rec.id, name))
        return result
    
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
    
    
    
##### Tabla Prestaciones
class HRPayroll_TablaPrestaciones(models.Model):
    _name = 'sat.nomina.tabla_prestaciones'
    _description = 'SAT - Tabla Prestaciones'

    @api.depends('sindicalizado', 'antiguedad')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Tipo Prestación: ') + dict(rec._fields['sindicalizado'].selection).get(rec.sindicalizado) + _(' - Antigüedad:') + str(rec.antiguedad)
            
            
    name = fields.Char('Descripción', store=True, compute='_compute_name')
    
    sindicalizado = fields.Selection([('Si','Sindicalizado'),
                                      ('No','De Confianza')],
                                     string="Tipo Prestación", default='No',
                                    required=True)
    
    antiguedad  = fields.Integer('Antigüedad', required=True, index=True)
    
    dias_vacaciones = fields.Integer('Días Vacaciones', required=True, default=0)
    prima_vacacional = fields.Float(string="% Prima Vac.", default=0,
                                   digits=(8,2))
    
    dias_aguinaldo = fields.Integer('Días Aguinaldo', required=True, default=0)
    
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, sindicalizado)', 'Tipo Prestación + Antigüedad deben ser únicos !'),
        ]

    _order = "sindicalizado, antiguedad"
    
    
