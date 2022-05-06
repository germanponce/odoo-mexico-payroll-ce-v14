# -*- coding: utf-8 -*-

{
    'name'          : 'Nóminas México - Integración - IMSS (SUA + IDSE)',
    'version'       : '1.0',
    'category'      : 'Vertical',
    'complexity'    : "easy",
    'description'   : """Nóminas México - IMSS""",
    'author'        : 'Argil Consulting',
    'website'       : 'http://www.argil.mx',
    'license': 'Other proprietary',
    'images' : [],
    'depends': ["hr", "hr_contract",
                "l10n_mx_payroll"],
    'data' : [
        'data/ir_sequence_data.xml',
        'data/res_country_state_data.xml',
        'views/res_country_state_view.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/hr_salary_rule_view.xml',
        'views/hr_employee_view.xml',
        'views/hr_contract_view.xml',
        'views/hr_settlement_view.xml',
        'views/hr_employee_imss_view.xml',
        'views/hr_employee_imss_sbc_view.xml',
        'views/hr_leave_view.xml',
        'views/hr_employee_imss_incapacity_view.xml',
        'views/hr_payslip_line_view.xml',
        'wizard/hr_employee_get_moves_view.xml',
        'wizard/hr_payslip_imss_wizard_view.xml',
        'wizard/hr_employee_get_sua_files_view.xml',
                ],
    'test': [],
    'demo': [],
    'installable': True,

}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
