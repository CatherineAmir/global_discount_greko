# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):

    _inherit = "sale.order"

    discount_type = fields.Selection(
        [("fixed", "Fixed"), ("percentage", "Percentage")], string="Discount Type",related='partner_id.discount_type',store=1,track_visibility='onchange'
    )
    discount_amount = fields.Float("Discount Amount",related='partner_id.discount_amount',store=1,track_visibility='onchange')

    customer_discount = fields.Monetary(string='Customer discount',compute="calculate_customer_discount", store=True,tracking=5,track_visibility='onchange')
    @api.constrains('discount_amount','discount_amount','order_line')
    def _calculate_discount(self):
        self.calculate_customer_discount()

