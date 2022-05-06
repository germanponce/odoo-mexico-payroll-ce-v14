# -*- coding: utf-8 -*-
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
from datetime import datetime, date, timedelta
import erppeek

odoo = erppeek.Client('https://erp-co.danone.com', 'erp-co', 'admin','4rg1l..')
#odoo2 = erppeek.Client('http://localhost:8069/jsonrpc', 'NOMINA_EE_14', 'admin','1')



aml_obj = odoo.model('account.move.line')

partidas = aml_obj.search([('journal_id','=',45),('credit','>',0), ('name','in',(False, '')),('move_id','=',9337)])
cont = 1
total = len(partidas)
for l in aml_obj.browse(partidas):
    print("Procesando %s de %s" % (cont, total))
    print("l.move_id.is_purchase_document(): %s" % l.move_id.is_purchase_document())
    print("id: %s - partner: %s - Cuenta: %s - %s - Account Type: %s" % (
        l.id, l.partner_id.id, 
        l.partner_id.property_account_payable_id.code, 
        l.partner_id.property_account_payable_id.name, 
        l.partner_id.property_account_payable_id.user_type_id.type))
    
    l.account_id=l.partner_id.property_account_payable_id.id
    cont += 1

exit()


select l.id, l.partner_id, 
    (select coalesce(select split_part(prop.value_reference,',',2) from ir_property prop
              where name='property_account_payable_id' and prop.fields_id=3481 and 
                prop.value_reference is not null and res_id is not null and
              split_part(res_id,',',1)='res.partner' and split_part(res_id,',',2):int = partner.id
              limit 1,
        select split_part(value_reference,',',2) from ir_property 
              where name='property_account_payable_id' and fields_id=3481 and 
                value_reference is not null and res_id is not null limit 1))::int account_id
    from account_move_line l 
    inner join res_partner partner on partner.id=l.partner_id
    
where (l.name is null or l.name='')
and l.journal_id=45;



select split_part(prop.value_reference,',',2) from ir_property prop
              where name='property_account_payable_id' and prop.fields_id=3481 and 
                prop.value_reference is not null and res_id is not null and
              split_part(res_id,',',1)='res.partner' and split_part(res_id,',',2) = 4318
              limit 1