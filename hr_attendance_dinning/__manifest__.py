# -*- encoding: utf-8 -*-

{
    "name" : "l10n_mx_payroll - Control de Asistencia a Comedor",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Payroll",
    "description" : """
    
    Este módulo permite llevar el registro de las asistencias a Comedor de los trabajadores
""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : [
                    "l10n_mx_payroll",
                    #"hr_attendance",
                    #"hr_contract",
                    #"hr_holidays",
                ],
    "data"    : [        
        'security/hr_attendance_dinning_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/hr_salary_rule_view.xml',
        'views/hr_dinning_view.xml',
                ],
    "installable" : True,
}
