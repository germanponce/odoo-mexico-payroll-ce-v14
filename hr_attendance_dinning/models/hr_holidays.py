# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime, timedelta, date
import logging
_logger = logging.getLogger(__name__)


class HRHolidays(models.Model):
    _inherit = 'hr.leave'

    
    def action_approve(self):
        res = super(HRHolidays, self).action_approve()
        dinning_att_obj = self.env['hr.attendance.dinning']
        for holiday in self.filtered(lambda w: w.employee_id and w.date_from and w.date_to):
            self.env.cr.execute("""
                    SELECT id
                    FROM hr_attendance_dinning
                    WHERE employee_id = %s AND date_record between %s and %s
                    ;""",
                    (holiday.employee_id.id, holiday.date_from.strftime('%Y-%m-%d %H:%M:%S'), holiday.date_to.strftime('%Y-%m-%d %H:%M:%S')))
            result = self.env.cr.fetchall()
            _logger.info("result: %s" % result)
            if result:
                result = [x and x[0] for x in result]
                attendances = dinning_att_obj.browse(result)
                attendances.unlink()

        return res
