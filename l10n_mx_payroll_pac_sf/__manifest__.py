# -*- encoding: utf-8 -*-

{
    "name" : "l10n_mx_payroll Conector PAC Solucion Factible",
    "version" : "1.0",
    "author" : "Argil Consulting",
    "category" : "Localization/Mexico",
    "description" : """
    
    This module is the connector to PAC Soluci&oacute;n Factible. 
    
    www.solucionfactible.com
    
    This module need this dependency:
Ubuntu Package Depends:
    sudo apt-get install python-soappy
""",
    "website" : "http://www.argil.mx",
    'license': 'Other proprietary',
    "depends" : ["l10n_mx_einvoice_pac_sf",
                 "l10n_mx_payroll",
                 "l10n_mx_payroll_argil"
    ],
    "data" : [],
    'installable': True,

}
