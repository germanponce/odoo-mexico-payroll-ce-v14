# -*- encoding: utf-8 -*-

{
    "name" : "Creador de Incidencias según asistencias - l10n_mx_payroll",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Localization/Mexico",
    "description" : """
    
    Crea las Incidencias según el registro de las Asistencias:
    - Retardos
    - Faltas (3 retardos en un periodo de nómina, o inasistencia del trabajador)
    - Horas Extras
    
""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : [
                    "hr_payroll",
                    "hr_attendance",
                    "l10n_mx_payroll",
                ],
    "data"    : [
                'security/ir.model.access.csv',
                 'data/hr_attendance_processor.xml',
                 'views/hr_employee_view.xml',
                 'views/hr_attendance_view.xml',
                 'views/res_company_view.xml',
                 'views/res_config_settings_view.xml',
                 'views/hr_payroll_structure_view.xml',
                ],
    "installable" : True,
}
