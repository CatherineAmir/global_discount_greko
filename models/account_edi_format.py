from odoo import fields, models, api, _
import json
import logging
import  base64
_logger = logging.getLogger(__name__)
DEFAULT_BLOCKING_LEVEL = 'error'
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
            'extraDiscountAmount': 0.0,
            'totalItemsDiscountAmount': self._l10n_eg_edi_round(totals['fixed_discount_total']),
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
            'fixed_discount_total':0.0,
            # 'customer_discount_total': 0.0,
        }
        for line in invoice.invoice_line_ids.filtered(lambda x: not ('discount' in x.name.lower())):
            line_tax_details = tax_data.get(line, {})
            price_unit = self._l10n_eg_edi_round(abs((line.balance / line.quantity) / (
                    1 - (line.discount / 100.0)))) if line.quantity and line.discount != 100.0 else line.price_unit
            price_subtotal_before_discount = self._l10n_eg_edi_round(abs(line.balance / (
                    1 - (line.discount / 100)))) if line.discount != 100.0 else price_unit * line.quantity
            # discount_amount = self._l10n_eg_edi_round(price_subtotal_before_discount - abs(line.balance))
            discount_amount = self._l10n_eg_edi_round(line.promotion_discount_unit*line.quantity)
            net_sales=self._l10n_eg_edi_round(abs(line.balance)-discount_amount)
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
                # customer_discount_unit
                'itemsDiscount': self._l10n_eg_edi_round(line.customer_discount_unit*line.quantity),
                'unitValue': {
                    'currencySold': invoice.currency_id.name,
                    'amountEGP': price_unit,
                },
                'discount': {
                    'rate': self._l10n_eg_edi_round(line.promotion_discount_unit*100/line.price_unit),
                    'amount': self._l10n_eg_edi_round(line.promotion_discount_unit*line.quantity),
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
                'netTotal': net_sales,
                'total': self._l10n_eg_edi_round(abs(net_sales + line_tax_details.get('tax_amount', 0.0)-self._l10n_eg_edi_round(line.customer_discount_unit*line.quantity))),
            })
            # print("line.move_id.discount_amount",line.move_id.discount_amount)
            # print("line.customer_discount_unit*line.quantity",line.customer_discount_unit*line.quantity)
            totals['discount_total'] += discount_amount  # before taxes
            totals['total_price_subtotal_before_discount'] += price_subtotal_before_discount
            totals['fixed_discount_total'] += self._l10n_eg_edi_round(line.customer_discount_unit*line.quantity)
            # totals['customer_discount_total']+=self._l10n_eg_edi_round(line.customer_discount_unit*line.quantity)
            if invoice.currency_id != self.env.ref('base.EGP'):
                lines[-1]['unitValue']['currencyExchangeRate'] = self._l10n_eg_edi_round(
                    invoice._l10n_eg_edi_exchange_currency_rate())
                lines[-1]['unitValue']['amountSold'] = line.price_unit
        # print("lines",lines)
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
        _logger.info("Partner come: {}".format(partner.name))
        _logger.info("Partner is issuer : {}".format(issuer))
        partner_name = partner.name
        if partner.parent_id:
            if  ']' in partner.parent_id.name or '[' in partner.parent_id.name :
                partner_name=partner.parent_id.name.split(']')[1]+','+partner.name.split(']')[1]
            else:
                partner_name=partner.parent_id.name+','+partner.name.split
        else:
            if ']' in partner.name:
                partner_name=partner.name.split(']')[1]
        _logger.info("Partner name: {}".format(partner_name))
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

    # def _post_invoice_edi(self, invoices):
    #     if self.code != 'eg_eta':
    #         return super()._post_invoice_edi(invoices)
    #     invoice = invoices  # Batching is disabled for this EDI.
    #
    #     # In case we have already sent it, but have not got a final answer yet.
    #     if invoice.l10n_eg_submission_number:
    #         return {invoice: self._l10n_eg_get_einvoice_status(invoice)}
    #
    #     if not invoice.l10n_eg_eta_json_doc_id:
    #         return {
    #             invoice: {
    #                 'error': _("An error occured in created the ETA invoice, please retry signing"),
    #                 'blocking_level': 'info'
    #             }
    #         }
    #     invoice_json = json.loads(invoice.l10n_eg_eta_json_doc_id.raw)['request']
    #     if not invoice_json.get('signatures'):
    #         return {
    #             invoice: {
    #                 'error': _("Please make sure the invoice is signed"),
    #                 'blocking_level': 'info'
    #             }
    #         }
    #     return {invoice: self._l10n_eg_edi_post_invoice_web_service(invoice)}
    #
    #     @api.model
    #     def _cron_process_documents_web_services(self, job_count=None):
    #         ''' Method called by the EDI cron processing all web-services.
    #
    #         :param job_count: Limit explicitely the number of web service calls. If not provided, process all.
    #         '''
    #         edi_documents = self.search([('state', 'in', ('to_send', 'to_cancel')), ('move_id.state', '=', 'posted'), ('l10n_eg_is_signed','=',True)])
    #         nb_remaining_jobs = edi_documents._process_documents_web_services(job_count=job_count)
    #
    #         # Mark the CRON to be triggered again asap since there is some remaining jobs to process.
    #         if nb_remaining_jobs > 0:
    #             self.env.ref('account_edi.ir_cron_edi_network')._trigger()
    #
    #         # action_retry_edi_documents_error

    @api.model
    def _process_job(self, documents, doc_type):
        """Post or cancel move_id (invoice or payment) by calling the related methods on edi_format_id.
        Invoices are processed before payments.

        :param documents: The documents related to this job. If edi_format_id does not support batch, length is one
        :param doc_type:  Are the moves of this job invoice or payments ?
        """
        # inherited
        def _postprocess_post_edi_results(documents, edi_result):
            attachments_to_unlink = self.env['ir.attachment']
            for document in documents:
                move = document.move_id
                # new
                if  move.error:
                    move.action_retry_edi_documents_error()
                move_result = edi_result.get(move, {})
                if move_result.get('attachment'):
                    old_attachment = document.attachment_id
                    document.attachment_id = move_result['attachment']
                    if not old_attachment.res_model or not old_attachment.res_id:
                        attachments_to_unlink |= old_attachment
                if move_result.get('success') is True:
                    document.write({
                        'state': 'sent',
                        'error': False,
                        'blocking_level': False,
                    })
                else:
                    document.write({
                        'error': move_result.get('error', False),
                        'blocking_level': move_result.get('blocking_level',
                                                          DEFAULT_BLOCKING_LEVEL) if 'error' in move_result else False,
                    })

            # Attachments that are not explicitly linked to a business model could be removed because they are not
            # supposed to have any traceability from the user.
            attachments_to_unlink.unlink()

        def _postprocess_cancel_edi_results(documents, edi_result):
            invoice_ids_to_cancel = set()  # Avoid duplicates
            attachments_to_unlink = self.env['ir.attachment']
            for document in documents:
                move = document.move_id
                move_result = edi_result.get(move, {})
                if move_result.get('success') is True:
                    old_attachment = document.attachment_id
                    document.write({
                        'state': 'cancelled',
                        'error': False,
                        'attachment_id': False,
                        'blocking_level': False,
                    })

                    if move.is_invoice(include_receipts=True) and move.state == 'posted':
                        # The user requested a cancellation of the EDI and it has been approved. Then, the invoice
                        # can be safely cancelled.
                        invoice_ids_to_cancel.add(move.id)

                    if not old_attachment.res_model or not old_attachment.res_id:
                        attachments_to_unlink |= old_attachment

                else:
                    document.write({
                        'error': move_result.get('error', False),
                        'blocking_level': move_result.get('blocking_level', DEFAULT_BLOCKING_LEVEL) if move_result.get(
                            'error') else False,
                    })

            if invoice_ids_to_cancel:
                invoices = self.env['account.move'].browse(list(invoice_ids_to_cancel))
                invoices.button_draft()
                invoices.button_cancel()

            # Attachments that are not explicitly linked to a business model could be removed because they are not
            # supposed to have any traceability from the user.
            attachments_to_unlink.unlink()

        documents.edi_format_id.ensure_one()  # All account.edi.document of a job should have the same edi_format_id
        documents.move_id.company_id.ensure_one()  # All account.edi.document of a job should be from the same company
        if len(set(doc.state for doc in documents)) != 1:
            raise ValueError('All account.edi.document of a job should have the same state')

        edi_format = documents.edi_format_id
        state = documents[0].state
        if doc_type == 'invoice':
            if state == 'to_send':
                invoices = documents.move_id
                with invoices._send_only_when_ready():
                    _logger.info('Invoice to sign %s',invoices)
                    edi_result = edi_format._post_invoice_edi(invoices)
                    _logger.info("here to after sign after sign %s", edi_result)
                    _postprocess_post_edi_results(documents, edi_result)
            elif state == 'to_cancel':
                edi_result = edi_format._cancel_invoice_edi(documents.move_id)
                _postprocess_cancel_edi_results(documents, edi_result)

        elif doc_type == 'payment':
            if state == 'to_send':
                edi_result = edi_format._post_payment_edi(documents.move_id)
                _postprocess_post_edi_results(documents, edi_result)
            elif state == 'to_cancel':
                edi_result = edi_format._cancel_payment_edi(documents.move_id)
                _postprocess_cancel_edi_results(documents, edi_result)

class EtaThumbDrive(models.Model):
    _inherit = 'l10n_eg_edi.thumb.drive'

    def action_sign_invoices(self, invoice_ids):
        self.ensure_one()
        sign_host = self._get_host()

        to_sign_dict = dict()
        for invoice_id in invoice_ids:
            # if invoice_id.l10n_eg_is_signed and not invoice_id.edi_error_message in ["An error occured in created the ETA invoice, please retry signing","Please make sure the invoice is signed"]:
            #     _logger.info("invoice not to sign %s",invoice_id.name)
            #     continue
            eta_invoice = json.loads(invoice_id.l10n_eg_eta_json_doc_id.raw)['request']
            signed_attrs = self._generate_signed_attrs(eta_invoice, invoice_id.l10n_eg_signing_time)
            to_sign_dict[invoice_id.id] = base64.b64encode(signed_attrs.dump()).decode()
        _logger.info("to_sign_dictn %s", json.dumps(to_sign_dict))
        return {
            'type': 'ir.actions.client',
            'tag': 'action_post_sign_invoice',
            'params': {
                'sign_host': sign_host,
                'access_token': self.access_token,
                'pin': self.pin,
                'drive_id': self.id,
                'invoices': json.dumps(to_sign_dict)
            }
        }

    def set_signature_data(self, invoices):
        """ This is called from the browser with the signed data from the local server """
        invoices = json.loads(invoices)

        for key, value in invoices.items():
            invoice_id = self.env['account.move'].browse(int(key))
            # if invoice_id.l10n_eg_is_signed or  invoice_id.edi_error_message not in ["An error occured in created the ETA invoice, please retry signing","Please make sure the invoice is signed"]:
            #     _logger.info("will not update signature %s",invoice_id.name)
            #     continue
            eta_invoice_json = json.loads(invoice_id.l10n_eg_eta_json_doc_id.raw)

            cades_bes = self._generate_cades_bes_signature(eta_invoice_json['request'], invoice_id.l10n_eg_signing_time,
                                                           base64.b64decode(value))
            signature = base64.b64encode(cades_bes.dump()).decode()

            eta_invoice_json['request']['signatures'] = [{'signatureType': 'I', 'value': signature}]
            invoice_id.l10n_eg_eta_json_doc_id.raw = json.dumps(eta_invoice_json)
            invoice_id.l10n_eg_is_signed = True
        return True



class AccountMove(models.Model):
    _inherit = 'account.move'
    edi_error_count = fields.Integer(
        compute='_compute_edi_error_count',
        help='How many EDIs are in error for this move ?',store=True)

    edi_error_message = fields.Html(
        compute='_compute_edi_error_message',store=True)