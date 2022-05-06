# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc



#odoo1 = odoorpc.ODOO('frigorificasonorensedj.odoo.com', port=80)
#odoo1.login('frigorificacontreras-master-940932', 'Argil', 'Nomina2020jc')

odoo1 = odoorpc.ODOO('odoo.jcvim.com.mx', port=80, version="12.0")
odoo1.login('FRIGORIFICA', 'rauliram2014@gmail.com', '2021')

odoo2 = odoorpc.ODOO('localhost', port=8069)
odoo2.login('DEMO_LM_NOMINAS_CE_14_SIFEI', 'admin', '1', version="14.0")


def get_code_from_string(cad):
    return cad.split(']')[0].replace('[','').replace(' ','')

# Categorias
rule_categ_obj1 = odoo1.env['hr.salary.rule.category']
rule_categ_obj2 = odoo2.env['hr.salary.rule.category']

category_ids = rule_categ_obj1.search_read([('code','!=',False),
                                            ('code','not in',('ALW','GROSS','BASIC','DED', 'COMP'))], 
                                           ['code','name','parent_id'],
                                           order='id')



for categ in category_ids:
    if categ['parent_id']:
        continue
    xcateg = rule_categ_obj2.search([('code','=',categ['code'])])
    if xcateg:
        print("Ya existe la categoria: %s - %s" % (categ['code'].encode('utf-8'), categ['name'].encode('utf-8')))
        continue
    print("Insertando Categoria: %s - %s" % (categ['code'].encode('utf-8'), categ['name'].encode('utf-8')))
    data = {'code' : categ['code'], 'name' : categ['name']}
    res = rule_categ_obj2.create(data)


for categ in category_ids:
    if not categ['parent_id']:
        continue
    xcateg = rule_categ_obj2.search([('code','=',categ['code'])])
    if xcateg:
        print("YA existe la categoria: %s - %s" % (categ['code'].encode('utf-8'), categ['name'].encode('utf-8')))
        continue
    print("Insertando Categoria: %s - %s" % (categ['code'].encode('utf-8'), categ['name'].encode('utf-8')))
    
    categ_id = rule_categ_obj2.search([('code','=', get_code_from_string(categ['parent_id'][1]))],limit=1)
    if not categ_id:
        exit()
    categ_id = categ_id[0]
    data = {'code' : categ['code'], 'name' : categ['name'], 'parent_id' : categ_id}
    res = rule_categ_obj2.create(data)

#Reglas

rule_obj1 = odoo1.env['hr.salary.rule']
rule_obj2 = odoo2.env['hr.salary.rule']
percep_obj2 = odoo2.env['sat.nomina.tipopercepcion']
deduc_obj2 = odoo2.env['sat.nomina.tipodeduccion']
incap_obj2 = odoo2.env['sat.nomina.tipoincapacidad']
otrop_obj2 = odoo2.env['sat.nomina.tipootropago']
rule_ids = rule_obj1.search_read([('code','!=',False),
                                  ('code','not in',('BASIC','GROSS'))], 
                                 ['code', 'name', 'category_id', 'sequence','tipo_movimiento',
                                  'no_suma','nomina_aplicacion',
                                  'appears_on_payslip', 'can_be_payroll_extra', 'es_subsidio_causado', 'is_dinning_attendance', 'tipo_gravable',
                                  'quantity', 'note', 'otro_clasificador', 'amount_fix', 'amount_percentage',
                                  'amount_percentage_base', 'amount_python_compute', 'amount_select', 'condition_python', 'condition_range',
                                  'condition_range_max', 'condition_range_min', 'condition_select', 'tipopercepcion_id' , 'tipodeduccion_id', 
                                  'tipootropago_id', 'tipoincapacidad_id',
            #'aplica_calculo_imss' : rule.aplica_calculo_imss,
            #'python_code_imss' : rule.python_code_imss,
                                 ],
                                 order='sequence asc')
for rule in rule_ids:
    print("======== Procesando: %s" % rule['name'])
    xrule = rule_obj2.search([('name','=',rule['name'])])
    if xrule:
        print("YA existe la Regla: %s - %s" % (rule['code'].encode('utf-8'), rule['name'].encode('utf-8')))
        print("Actualizando codigo para la regla...")
        percep_id, deduc_id, otrop_id, incap_id = False, False, False, False
        if rule['nomina_aplicacion']=='percepcion':
            percep_id = percep_obj2.search([('code','=', get_code_from_string(rule['tipopercepcion_id'][1]))], limit=1)[0]
            
        elif rule['nomina_aplicacion']=='deduccion':
            deduc_id = deduc_obj2.search([('code','=', get_code_from_string(rule['tipodeduccion_id'][1]))], limit=1)[0]

        elif rule['nomina_aplicacion']=='otrospagos':
            otrop_id = otrop_obj2.search([('code','=', get_code_from_string(rule['tipootropago_id'][1]))], limit=1)[0]

        elif rule['nomina_aplicacion']=='incapacidad':
            incap_id = incap_obj2.search([('code','=', get_code_from_string(rule['tipoincapacidad_id'][1]))], limit=1)[0]

        data = {
            'name' : rule['name'],
            'sequence'      : rule['sequence'],
            'tipo_movimiento' : 'na',
            'no_suma'       : rule['no_suma'],
            'nomina_aplicacion' : rule['nomina_aplicacion'],
            'appears_on_payslip': rule['appears_on_payslip'],
            'can_be_payroll_extra' : rule['can_be_payroll_extra'],
            'es_subsidio_causado' : rule['es_subsidio_causado'],
            'is_dinning_attendance' : rule['is_dinning_attendance'],
            'tipo_gravable' : rule['tipo_gravable'],
            'quantity'      : rule['quantity'],
            'note'          : rule['note'],
            'otro_clasificador' : rule['otro_clasificador'],
            'amount_fix'    : rule['amount_fix'],
            'amount_percentage' : rule['amount_percentage'],
            'amount_percentage_base': rule['amount_percentage_base'],
            'amount_python_compute' : rule['amount_python_compute'],
            'amount_select' : rule['amount_select'],
            'condition_python' : rule['condition_python'],
            'condition_range' : rule['condition_range'],
            'condition_range_max' : rule['condition_range_max'],
            'condition_range_min' : rule['condition_range_min'],
            'condition_select' : rule['condition_select'],
            'tipopercepcion_id' : percep_id,
            'tipodeduccion_id' : deduc_id, 
            'tipootropago_id' : otrop_id, 
            'tipoincapacidad_id' : incap_id,
            #'aplica_calculo_imss' : rule.aplica_calculo_imss,
            #'python_code_imss' : rule.python_code_imss,
        }
        print ("===== ===== ===== =====")
        print("xrule: %s" % xrule)
        xrule_rec = rule_obj2.browse(xrule)
        cadena = '\n'
        data2 = data.copy()
        for x in data2.keys():
            if not data[x]:
                data.pop(x)
        xrule_rec.write(data)
    else:
        print("=== Insertando: %s - %s ===" % (rule['code'].encode('utf-8'), rule['name'].encode('utf-8')))
        categ_id = rule_categ_obj2.search([('code','=',get_code_from_string(rule['category_id'][1]))],limit=1)

        if not categ_id:
            print("ERROR !!! No se encontro la categoria: %s" % (rule['category_id'].encode('utf-8')))
            exit()
        categ_id = categ_id[0]
        percep_id, deduc_id, otrop_id, incap_id = False, False, False, False
        if rule['nomina_aplicacion']=='percepcion':
            try:
                percep_id = percep_obj2.search([('code','=', get_code_from_string(rule['tipopercepcion_id'][1]))], limit=1)[0]
            except:
                print("rule: %s - %s - %s" % (rule['code'], rule['name'], rule['tipopercepcion_id'][1]))
                print("%s" % (1,2,3))
        elif rule['nomina_aplicacion']=='deduccion':
            deduc_id = deduc_obj2.search([('code','=', get_code_from_string(rule['tipodeduccion_id'][1]))], limit=1)[0]
        elif rule['nomina_aplicacion']=='otrospagos':
            otrop_id = otrop_obj2.search([('code','=', get_code_from_string(rule['tipootropago_id'][1]))], limit=1)[0]
        elif rule['nomina_aplicacion']=='incapacidad':
            incap_id = incap_obj2.search([('code','=', get_code_from_string(rule['tipoincapacidad_id'][1]))], limit=1)[0]

        data = {
            'code'          : rule['code'],
            'name'          : rule['name'],
            'sequence'      : rule['sequence'],
            'tipo_movimiento' : 'na',
            'category_id'   : categ_id,
            'no_suma'       : rule['no_suma'],
            'nomina_aplicacion' : rule['nomina_aplicacion'],
            'appears_on_payslip': rule['appears_on_payslip'],
            'can_be_payroll_extra' : rule['can_be_payroll_extra'],
            'es_subsidio_causado' : rule['es_subsidio_causado'],
            #'is_dinning_attendance' : rule.is_dinning_attendance,
            'tipo_gravable' : rule['tipo_gravable'],
            'quantity'      : rule['quantity'],
            'note'          : rule['note'],
            'otro_clasificador' : rule['otro_clasificador'],
            'amount_fix'    : rule['amount_fix'],
            'amount_percentage' : rule['amount_percentage'],
            'amount_percentage_base': rule['amount_percentage_base'],
            'amount_python_compute' : rule['amount_python_compute'],
            'amount_select' : rule['amount_select'],
            'condition_python' : rule['condition_python'],
            'condition_range' : rule['condition_range'],
            'condition_range_max' : rule['condition_range_max'],
            'condition_range_min' : rule['condition_range_min'],
            'condition_select' : rule['condition_select'],
            'tipopercepcion_id' : percep_id,
            'tipodeduccion_id' : deduc_id, 
            'tipootropago_id' : otrop_id, 
            'tipoincapacidad_id' : incap_id,
            #'aplica_calculo_imss' : rule.aplica_calculo_imss,
            #'python_code_imss' : rule.python_code_imss,
        }
        #print("data: %s" % data)
        res = rule_obj2.create(data)


# Estructuras

struc_obj1 = odoo1.env['hr.payroll.structure']
struc_obj2 = odoo2.env['hr.payroll.structure']

struc_ids = struc_obj1.search([])

for struct in struc_obj1.browse(struc_ids):
    xstruct = struc_obj2.search([('code','=',struct.code),('code','!=','BASE')])
    if xstruct:
        print("YA existe la Estructura Salarial: %s - %s" % (struct.code.encode('utf-8'), struct.name.encode('utf-8')))
        continue
    print("===== Insertando: %s - %s" % (struct.code.encode('utf-8'), struct.name.encode('utf-8')))

    rule_ids = []
    for rule in struct.rule_ids:
        xrule = rule_obj2.search([('name','=',rule.name)], limit=1)
        if not xrule:
            print("Error, no se encontro la Regla: %s - %s" % (rule.code.encode('utf-8'), rule.name.encode('utf-8')))
        rule_ids.append(xrule[0])
    data = {'code' : struct.code,
            'name' : struct.name,
            'parent_id' : False,
            'rule_ids' : [(6, 0, rule_ids)]}
    res = struc_obj2.create(data)

exit()

