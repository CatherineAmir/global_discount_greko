# -*- coding: utf-8 -*-
# from odoo import http


# class SitaDiscountEta(http.Controller):
#     @http.route('/sita_discount_eta/sita_discount_eta', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sita_discount_eta/sita_discount_eta/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sita_discount_eta.listing', {
#             'root': '/sita_discount_eta/sita_discount_eta',
#             'objects': http.request.env['sita_discount_eta.sita_discount_eta'].search([]),
#         })

#     @http.route('/sita_discount_eta/sita_discount_eta/objects/<model("sita_discount_eta.sita_discount_eta"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sita_discount_eta.object', {
#             'object': obj
#         })
