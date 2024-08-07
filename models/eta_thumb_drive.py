from odoo import fields, models, api
import json
import base64
from odoo.exceptions import ValidationError



class EtaThumbDrive(models.Model):
    _inherit = 'l10n_eg_edi.thumb.drive'
    def set_certificate(self, certificate):
        try:
            """ This is called from the browser to set the certificate"""
            self.ensure_one()
            self.certificate = certificate.encode()
        except Exception as e:
            raise ValidationError("error occured while setting")

        return True

    def set_signature_data(self, invoices):
        """ This is called from the browser with the signed data from the local server """
        try:
            invoices = json.loads(invoices)
            for key, value in invoices.items():
                invoice_id = self.env['account.move'].browse(int(key))
                eta_invoice_json = json.loads(invoice_id.l10n_eg_eta_json_doc_id.raw)

                cades_bes = self._generate_cades_bes_signature(eta_invoice_json['request'], invoice_id.l10n_eg_signing_time,
                                                         base64.b64decode(value))

                try:
                    signature=cades_bes


                    # signature = (base64.b64encode(cades_bes.encode())).decode("utf-8")

                except Exception as e:
                    invoice_id.message_post(body="error in signature_line {}".format(str(e)))
                else:


                    eta_invoice_json['request']['signatures'] = [{'signatureType': 'I', 'value': signature}]
        
                    invoice_id.l10n_eg_eta_json_doc_id.raw = json.dumps(eta_invoice_json)
                    invoice_id.l10n_eg_is_signed = True
        except Exception as e:
            if invoice_id:
                invoice_id.message_post(body="An error occurred while set signature data {}".format(e))
        else:
            return True
