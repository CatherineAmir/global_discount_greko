from odoo import fields, models, api, _


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    @api.model
    def _l10n_eg_eta_prepare_eta_invoice(self, invoice):
        def group_tax_retention(tax_values):
            return {'l10n_eg_eta_code': tax_values['tax_id'].l10n_eg_eta_code.split('_')[0]}

        invoice.calculate_total_discount()
        date_string = invoice.invoice_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        grouped_taxes = invoice._prepare_edi_tax_details(grouping_key_generator=group_tax_retention)
        invoice_line_data, totals = self._l10n_eg_eta_prepare_invoice_lines_data(invoice, grouped_taxes[
            'invoice_line_tax_details'])
        eta_invoice = {
            'issuer': self._l10n_eg_eta_prepare_address_data(invoice.journal_id.l10n_eg_branch_id, invoice,
                                                             issuer=True, ),
            'receiver': self._l10n_eg_eta_prepare_address_data(invoice.partner_id, invoice),
            'documentType': 'i' if invoice.move_type == 'out_invoice' else 'c' if invoice.move_type == 'out_refund' else 'd' if invoice.move_type == 'in_refund' else '',
            'documentTypeVersion': '1.0',
            'dateTimeIssued': date_string,
            'taxpayerActivityCode': invoice.journal_id.l10n_eg_activity_type_id.code,
            'internalID': invoice.name,
        }
        eta_invoice.update({
            'invoiceLines': invoice_line_data,
            'taxTotals': [{
                'taxType': tax['l10n_eg_eta_code'].split('_')[0].upper(),
                'amount': self._l10n_eg_edi_round(abs(tax['tax_amount'])),
            } for tax in grouped_taxes['tax_details'].values()],
            'totalDiscountAmount': self._l10n_eg_edi_round(totals['discount_total']),
            'totalSalesAmount': self._l10n_eg_edi_round(totals['total_price_subtotal_before_discount']),
            'netAmount': self._l10n_eg_edi_round(
                totals['total_price_subtotal_before_discount'] - totals['discount_total']),
            'totalAmount': self._l10n_eg_edi_round(abs(invoice.amount_total_signed)),
            'extraDiscountAmount': self._l10n_eg_edi_round(abs(invoice.discount)),
            'totalItemsDiscountAmount': 0.0,
        })
        if invoice.ref:
            eta_invoice['purchaseOrderReference'] = invoice.ref
        if invoice.extra_note:
            if invoice.extra_note.striptags() !='':
                eta_invoice['salesOrderReference'] = invoice.extra_note.striptags()

        # print('eta_invoice',eta_invoice)
        return eta_invoice

    @api.model
    def _l10n_eg_eta_prepare_invoice_lines_data(self, invoice, tax_data):
        lines = []
        totals = {
            'discount_total': 0.0,
            'total_price_subtotal_before_discount': 0.0,
        }
        for line in invoice.invoice_line_ids.filtered(lambda x: not ('discount' in x.name.lower())):
            line_tax_details = tax_data.get(line, {})
            price_unit = self._l10n_eg_edi_round(abs((line.balance / line.quantity) / (
                    1 - (line.discount / 100.0)))) if line.quantity and line.discount != 100.0 else line.price_unit
            price_subtotal_before_discount = self._l10n_eg_edi_round(abs(line.balance / (
                    1 - (line.discount / 100)))) if line.discount != 100.0 else price_unit * line.quantity
            discount_amount = self._l10n_eg_edi_round(price_subtotal_before_discount - abs(line.balance))
            item_code = line.product_id.l10n_eg_eta_code or line.product_id.barcode
            lines.append({
                'description': line.name,
                'itemType': item_code.startswith('EG') and 'EGS' or 'GS1',
                'itemCode': item_code,
                'unitType': line.product_uom_id.l10n_eg_unit_code_id.code,
                'quantity': line.quantity,
                'internalCode': line.product_id.default_code or '',
                'valueDifference': 0.0,
                'totalTaxableFees': 0.0,
                'itemsDiscount': 0.0,
                'unitValue': {
                    'currencySold': invoice.currency_id.name,
                    'amountEGP': price_unit,
                },
                'discount': {
                    'rate': line.discount,
                    'amount': discount_amount,
                },
                'taxableItems': [
                    {
                        'taxType': tax['tax_id'].l10n_eg_eta_code.split('_')[0].upper().upper(),
                        'amount': self._l10n_eg_edi_round(abs(tax['tax_amount'])),
                        'subType': tax['tax_id'].l10n_eg_eta_code.split('_')[1].upper(),
                        'rate': abs(tax['tax_id'].amount),
                    }
                    for tax_details in line_tax_details.get('tax_details', {}).values() for tax in
                    tax_details.get('group_tax_details')
                ],
                'salesTotal': price_subtotal_before_discount,
                'netTotal': self._l10n_eg_edi_round(abs(line.balance)),
                'total': self._l10n_eg_edi_round(abs(line.balance + line_tax_details.get('tax_amount', 0.0))),
            })
            totals['discount_total'] += discount_amount  # before taxes
            totals['total_price_subtotal_before_discount'] += price_subtotal_before_discount
            if invoice.currency_id != self.env.ref('base.EGP'):
                lines[-1]['unitValue']['currencyExchangeRate'] = self._l10n_eg_edi_round(
                    invoice._l10n_eg_edi_exchange_currency_rate())
                lines[-1]['unitValue']['amountSold'] = line.price_unit
        return lines, totals

    def _check_move_configuration(self, invoice):

        errors = []

        if invoice.journal_id.l10n_eg_branch_id.vat == invoice.partner_id.vat:
            errors.append(_("You cannot issue an invoice to a partner with the same VAT number as the branch."))
        if not self._l10n_eg_get_eta_token_domain(invoice.company_id.l10n_eg_production_env):
            errors.append(_("Please configure the token domain from the system parameters"))
        if not self._l10n_eg_get_eta_api_domain(invoice.company_id.l10n_eg_production_env):
            errors.append(_("Please configure the API domain from the system parameters"))
        if not all([invoice.journal_id.l10n_eg_branch_id, invoice.journal_id.l10n_eg_branch_identifier,
                    invoice.journal_id.l10n_eg_activity_type_id]):
            errors.append(_("Please set the all the ETA information on the invoice's journal"))
        if not self._l10n_eg_validate_info_address(invoice.journal_id.l10n_eg_branch_id):
            errors.append(_("Please add all the required fields in the branch details"))
        if not self._l10n_eg_validate_info_address(invoice.partner_id, invoice=invoice):
            errors.append(_("Please add all the required fields in the customer details"))
        if not all(aml.product_uom_id.l10n_eg_unit_code_id.code for aml in
                   invoice.invoice_line_ids.filtered(lambda x: not (x.display_type or 'discount' in x.name.lower()))):
            print("invoice.invoice_line_ids.filtered(lambda x: not (x.display_type or x.name=='Discount')",
                  invoice.invoice_line_ids.filtered(lambda x: not (x.display_type or 'discount' in x.name.lower())))
            errors.append(_("Please make sure the invoice lines UoM codes are all set up correctly"))
        if not all(tax.l10n_eg_eta_code for tax in invoice.invoice_line_ids.filtered(
                (lambda x: not (x.display_type or 'discount' in x.name.lower()))).tax_ids):
            errors.append(_("Please make sure the invoice lines taxes all have the correct ETA tax code"))
        if not all(aml.product_id.l10n_eg_eta_code or aml.product_id.barcode for aml in
                   invoice.invoice_line_ids.filtered(lambda x: not (x.display_type or 'discount' in x.name.lower()))):
            errors.append(_("Please make sure the EGS/GS1 Barcode is set correctly on all products"))
        return errors

    @api.model
    def _l10n_eg_eta_prepare_address_data(self, partner, invoice, issuer=False):
        if partner.parent_id:
            if  ']' in partner.parent_id.name or '[' in partner.parent_id.name :
                partner_name=partner.parent_id.name.split(']')[1]+','+partner.name.split(']')[1]
            else:
                partner_name=partner.parent_id.name+','+partner.name.split
        else:

            partner_name=partner.name.split('[')[0]
        address = {
            'address': {
                'country': partner.country_id.code,
                'governate': partner.state_id.name or '',
                'regionCity': partner.city or '',
                'street': partner.street or '',
                'buildingNumber': partner.l10n_eg_building_no or '',
                'postalCode': partner.zip or '',
            },

            'name': partner_name
        }
        if issuer:
            address['address']['branchID'] = invoice.journal_id.l10n_eg_branch_identifier or ''
        individual_type = self._l10n_eg_get_partner_tax_type(partner, issuer)
        address['type'] = individual_type or ''
        if invoice.amount_total >= invoice.company_id.l10n_eg_invoicing_threshold or individual_type != 'P':
            address['id'] = partner.vat or ''
        return address

    # @api.model
    # def _l10n_eg_validate_info_address(self, partner_id, issuer=False, invoice=False):
    #     fields = ["country_id",
    #               "state_id", "city", "street",
    #               "l10n_eg_building_no"]
    #     print('type',partner_id.name,self._l10n_eg_get_partner_tax_type(partner_id, issuer))
    #     if self._l10n_eg_get_partner_tax_type(partner_id, issuer)=='P':
    #         fields=["country_id"]
    #     if (
    #             invoice and invoice.amount_total >= invoice.company_id.l10n_eg_invoicing_threshold) or self._l10n_eg_get_partner_tax_type(
    #         partner_id, issuer) != 'P':
    #         fields.append('vat')
    #     print('all(partner_id[field] for field in fields)',all(partner_id[field] for field in fields))
    #     print('fields',fields)
    #     return all(partner_id[field] for field in fields)
    #
    # @api.model
    # def _l10n_eg_get_partner_tax_type(self, partner_id, issuer=False):
    #     if issuer:
    #         return 'B'
    #     elif partner_id.commercial_partner_id.country_code == 'EG':
    #         return 'B' if partner_id.commercial_partner_id.is_company and partner_id.commercial_partner_id.id != partner_id.id else 'P'
    #     else:
    #         return 'F'
