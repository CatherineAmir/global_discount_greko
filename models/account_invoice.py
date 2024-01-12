# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountInvoice(models.Model):

    _inherit = "account.move"

    discount_type = fields.Selection(
        [("fixed", "Fixed"), ("percentage", "Percentage")], string="Discount Type",related='partner_id.discount_type')
    discount_amount = fields.Float("Discount Amount",related='partner_id.discount_amount',store=1)
    customer_discount = fields.Monetary("Customer Discount", compute="calculate_customer_discount", store=True,copy=False)

    @api.depends("discount_amount", "discount_type")
    def calculate_customer_discount(self):
        pass



class res_config_settings(models.TransientModel):

    _inherit = "res.config.settings"

    discount_id = fields.Many2one(
        "account.account",
        "Discount",
        domain=[("internal_type", "not in", ["receivable", "payable"])],
    )

    def set_values(self):
        super(res_config_settings, self).set_values()
        IrDefault = self.env["ir.default"].sudo()
        IrDefault.set("res.config.settings", "discount_id", self.discount_id.id)

    @api.model
    def get_values(self):
        res = super(res_config_settings, self).get_values()
        IrDefault = self.env["ir.default"].sudo()
        res.update(discount_id=IrDefault.get("res.config.settings", "discount_id"))
        return res
