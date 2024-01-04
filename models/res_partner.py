from odoo import fields, models, api


class Partner(models.Model):
    _inherit = 'res.partner'
    discount_type = fields.Selection(
        [("fixed", "Fixed"), ("percentage", "Percentage")], string = "Discount Type",
    )

    discount_amount = fields.Float("Discount Amount")

    @api.onchange('child_ids', 'discount_type', 'discount_amount')
    def child_discount(self):
        for r in self:
            if r.child_ids:

                child_ids=self.env['res.partner'].search([('parent_id.id','=',r._origin.id)])
                for c in child_ids:
                    c.discount_type = r.discount_type
                    c.discount_amount =r.discount_amount


    @api.depends('child_ids', 'discount_type', 'discount_amount')
    def _child_discount(self):
        for r in self:
            r.discount_amount()
