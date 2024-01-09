# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Sale Discount With Accounting Entry",
    "author": "Warlock Technologies Pvt Ltd.",
    "description": """Global Discount
====================================
This module allow to set discount globaly on sale order and direct on invoice.
which will also have the impact on journal entry.
    """,
    "summary": """Global Discount With Accounting Entry""",
    "version": "15.0.1.0",
    "price": 20.00,
    "currency": "USD",
    "license": "OPL-1",
    "support": "info@warlocktechnologies.com",
    "website": "http://warlocktechnologies.com",
    "category": "Sales",
    "depends": ["sale_management", "account"],
    "images": ["images/screen_image.png"],
    "data": [
              "view/sale_order_view.xml",
             "view/account_invoice_view.xml",
             "view/res_partner_view.xml",
             "view/partner_actions.xml",

    ],
    "installable": True,
}

