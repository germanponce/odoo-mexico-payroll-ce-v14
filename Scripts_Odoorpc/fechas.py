# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import odoorpc


odoo = odoorpc.ODOO('linte.odoo.com', port=80)

# Login
odoo.login('linte', 'victor.villazon@proktive.com', 'villas01A*')

def payment_is_credit(payment_term):
    if not payment_term:
        return False
    term_ids = payment_term.line_ids
    if len(term_ids) == 1 \
        and term_ids.value == 'balance' \
        and term_ids.option == 'day_after_invoice_date' \
        and term_ids.days == 0:
        return False
    return True


partner_obj = odoo.env['res.partner']
user_obj = odoo.env['res.users']
so_obj = odoo.env['sale.order']

record = so_obj.browse(4096)
partner = partner_obj.browse(136)
user = user_obj.browse(9)
omit_limits = False #user.has_group('__export__.group_omit_credit_limit')
print("omit_limits: %s" % omit_limits)

# If partner doesn't have credit limit we can only sale with inmediate payment
if payment_is_credit(record.payment_term_id) and partner.x_credit_limit == 0 and not omit_limits:
    print('El cliente %s no tiene limite de credito configurado. No puede hacerle ventas a credito' % record.partner_id.name)

# If partner have credit limit we check if have enough for this sale
if partner.x_credit_limit > 0 and not omit_limits:
    #lang_code = model._context.get('lang', 'en_US')
    date_format = '%Y-%m-%d'
    moveline_obj = odoo.env['account.move.line']
    movelines = moveline_obj.search([
      ('partner_id', '=', partner.id),
      ('account_id.internal_type', 'in', ['receivable', 'payable']),
      ('move_id.state', '=', 'posted'),
      ('full_reconcile_id', '=', False),
      #('reconciled', '=', False),
     ])
    debit_maturity, debit, credit = 0.0, 0.0, 0.0
    today_dt = datetime.now()
    for line in moveline_obj.browse(movelines):
        
        limit_date = datetime.strptime(line.date_maturity.strftime(date_format), date_format)
        debit += line.debit
        credit += line.credit
        if limit_date <= today_dt:
            debit_maturity += line.debit
    balance_total = debit - credit
    balance_maturity = debit_maturity - credit if debit_maturity else 0.0

    if balance_maturity != 0 or (balance_total + record.amount_total) > partner.x_credit_limit:
        msg = ('La orden de venta no puede ser confirmada porque el cliente excede su límite de crédito o tiene pagos retrasados.\n'
               'Por favor pague el monto retrasado o revise el límite de crédito.\n\n'
               'Límite de crédito: %.2f\n'
               'Saldo a la fecha: %.2f (serían %.2f con esta orden)\n'
               'Pago retrasado: %.2f') % (
                partner.x_credit_limit,
                balance_total,
                balance_total + record.amount_total,
                balance_maturity)
        raise Warning('Límite de crédito excedido!\n' + msg)
exit()