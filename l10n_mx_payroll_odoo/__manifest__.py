# coding: utf-8
#
{
    "name": "Nómina Mexicana con LM Odoo",
    "version": "1.0",
    "author": "Argil Consulting",
    "category": "HR",
    "website": "http://www.argil.mx/",
    "depends": [
        "l10n_mx_payroll", 
        "l10n_mx_edi_extended"],
    "demo": [],
    "data": [
        'template/cfdi_40.xml',
        'report/l10n_mx_payroll_report.xml',
        'views/hr_payslip_view.xml'],
    "test": [],
    "js": [],
    "css": [],
    "qweb": [],
    "installable": True,
    'license': 'Other proprietary',
}
