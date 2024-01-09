# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class account_invoice(models.Model):

    _inherit = "account.move"

    discount_type = fields.Selection(
        [("fixed", "Fixed"), ("percentage", "Percentage")], string="Discount Type"
    )
    discount_amount = fields.Float("Discount Amount")
    discount = fields.Monetary("Discount", compute="calculate_discount", store=True,copy=False)

    @api.depends("discount_amount", "discount_type")
    def calculate_discount(self):
        for rec in self:
            if rec.discount_amount < 0:
                raise UserError(
                    _(
                        "Discount Amount Must be zero OR grater than zero OR positive amount"
                    )
                )
            elif rec.discount_type == "fixed":
                rec.discount = rec.discount_amount
                rec.amount_total -= rec.discount_amount
                if rec.discount > rec.amount_untaxed:
                    raise UserError(_("Discount Must be less than total amount"))
            elif rec.discount_type == "percentage":
                total = (rec.amount_untaxed * rec.discount_amount) / 100
                rec.discount = total
                rec.amount_total -= total
                if rec.discount > rec.amount_untaxed:
                    raise UserError(_("Discount Must be less than total amount"))

    def write(self, vals):
        res = super(account_invoice, self).write(vals)
        if vals.get('discount_amount') or vals.get('discount_type'):
            self.action_add_discount_journal_entry()
        return res

    @api.model
    def create(self, vals):
        res = super(account_invoice, self).create(vals)
        if vals.get('discount_amount') or vals.get('discount_type'):
            # res.action_add_discount_journal_entry()
            pass
        return res

    def action_add_discount_journal_entry(self):
        discount = self.env["ir.default"].get("res.config.settings", "discount_id")
        discount_line = self.invoice_line_ids.filtered(lambda a: a.account_id.id == discount or 'discount' in a.name.lower())
        journal_line = self.line_ids.filtered(lambda a: a.account_id.id == discount or 'discount' in a.name.lower())
        vals = {
                    'name': 'Discount',
                    'price_unit': -abs(self.discount),
                    'price_subtotal': -abs(self.discount),
                    'move_id': self.id,
                    'account_id': discount,
        }
        if not discount_line:
            self.write({
                    'invoice_line_ids': [(0,0, vals)]
            })
        if discount_line:
            pass
            # raise UserError(
            #         _(
            #             "Discount is already added !!"
            #         )
            #     )

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
