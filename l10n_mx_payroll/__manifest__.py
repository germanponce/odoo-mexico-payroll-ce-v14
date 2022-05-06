# coding: utf-8
#
{
    "name": "Nómina para México",
    "version": "1.0",
    "author": "Argil Consulting",
    "category": "HR",
    "website": "http://www.argil.mx/",
    "depends": [
        "hr_payroll_account_community", 
        "hr_holidays"
        ],
    "demo": [],
    "data": [
        "data/causa_terminacion_relacion_laboral_data.xml",
        "security/hr_payroll_security.xml",
        "security/ir.model.access.csv",
        "data/hr_payroll_data.xml",
        "data/ir_sequence_data.xml",
        "data/hr_holidays_status_data.xml",
        "data/hr_payroll_scheduler_data.xml",
        "data/ir_cron_data.xml",
        "views/extra_data_view.xml",
        "views/hr_department_view.xml",
        "views/res_config_settings_view.xml",
        "views/hr_employee_view.xml",
        "wizard/upload_data_view.xml",
        "wizard/sat_catalogos_view.xml",
        "views/hr_contract_view.xml",
        "views/hr_holidays_view.xml",
        "views/hr_salary_rule_view.xml",
        "views/hr_holidays_control_view.xml",
        "wizard/report_payroll_list_wizard_view.xml",
        "views/hr_payslip_view.xml",
        "template/cfdi.xml",
        "report/l10n_mx_payroll_report.xml",
        "report/report_payroll_list.xml",
        "report/hr_settlement_report.xml",
        "report/report_hr_payslip.xml",
        "template/hr_payslip_mail_template.xml",
        "views/hr_payslip_extra_view.xml",
        "views/hr_settlement_view.xml",
        'views/hr_payslip_analysis_view.xml',
        "views/hr_payslip_employees_view.xml",
        "wizard/hr_payslip_input_reschedule_view.xml",
        "views/hr_payroll_period_view.xml",
        "wizard/hr_contract_sueldo_inverso_view.xml",
        "views/hr_contract_aumento_masivo_view.xml",
        "wizard/hr_payslip_extra_import_view.xml",
        "wizard/hr_payslip_cancel_sat_view.xml",
    ],
    "test": [],
    "js": [],
    "css": [],
    "qweb": [],
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
    'license': 'Other proprietary',
}
