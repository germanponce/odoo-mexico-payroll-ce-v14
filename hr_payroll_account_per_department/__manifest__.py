# -*- encoding: utf-8 -*-

{
    "name" : "Nómina - Contabilizar Regla Salarial por Departamento",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Payroll",
    "description" : """
    
    Este módulo agrega campos en las reglas salariales para poder 
    configurar cuentas contables según el departamento del trabajador.
    
""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : [
        #"hr_payroll_account",
        "l10n_mx_payroll",
                ],
    "data"    : [
        'security/ir.model.access.csv',
        'views/hr_salary_rule_view.xml',
        'views/hr_payslip_view.xml'
],
    "installable" : True,
}
