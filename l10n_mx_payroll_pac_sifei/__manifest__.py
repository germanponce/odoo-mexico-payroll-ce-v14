# -*- encoding: utf-8 -*-

{
    "name" : "l10n_mx_payroll Conector PAC SIFEI",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Localization/Mexico",
    "description" : """
    
    This module is the connector to PAC SIFEI for l10n_mx_payroll_argil
    
    www.sifei.com.mx
    
    This module need this dependency:
Ubuntu Package Depends:
    sudo apt-get install python-suds
""",
    "website" : "http://www.argil.mx",
    "depends" : [
                    "l10n_mx_einvoice_pac_sifei",
                    "l10n_mx_payroll_argil",
                ],
    "data"    : [],
    'installable': True,
    'license': 'Other proprietary',
}
