# -*- encoding: utf-8 -*-

{
    "name" : "l10n_mx_payroll Reenviar Recibo por Correo",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Localization/Mexico",
    "description" : """
    
    Reenviar Recibo por Correo
    

""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : [
        "hr_payroll",
        "l10n_mx_payroll",
    ],
    "data" : [
        'security/ir.model.access.csv',
        'hr_payslip_resend_mail_view.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,

}
