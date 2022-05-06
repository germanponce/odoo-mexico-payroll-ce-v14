# -*- encoding: utf-8 -*-

{
    "name" : "Nómina - Dispersión Analítica de Partidas de Nómina",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Payroll",
    "description" : """
    
    Este módulo hace la dispersión analítica de las partidas contables
    de una lista de nómina de acuerdo a un archivo CSV con las siguientes
    características:
    
    Nombre,Porcentaje,Cuenta Analítica
    Juan Pérez Martínez,20.0,100.01.224
    Juan Pérez Martínez,40.0,100.01.124
    Juan Pérez Martínez,40.0,100.02.225
    
""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : [
        "hr_payroll_account_per_department",
        "l10n_mx_payroll",
                ],
    "data"    : [
        'views/hr_payslip_view.xml',
],
    "installable" : False,
}
