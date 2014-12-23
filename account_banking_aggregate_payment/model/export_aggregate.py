# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    This module copyright (C) 2013 Therp BV (<http://therp.nl>).
#    Contributors: credativ ltd (<http://www.credativ.co.uk>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
from openerp.tools.translate import _
from openerp import netsvc


class banking_export_aggregate(orm.TransientModel):
    _name = 'banking.export.aggregate'
    _description = 'Execute aggregate payment order'
    _rec_name = 'payment_order_id'

    _columns = {
        'payment_order_id': fields.many2one(
            'payment.order', 'Payment order',
            required=True),
        }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if not vals.get('payment_order_id'):
            if not context.get('active_ids'):
                raise orm.except_orm(
                    _('Error'),
                    _('Please select a payment order'))
            if len(context['active_ids']) > 1:
                raise orm.except_orm(
                    _('Error'),
                    _('Please only select a single payment order'))
            vals['payment_order_id'] = context['active_ids'][0]
        return super(banking_export_aggregate, self).create(
            cr, uid, vals, context=context)

    def reconcile_lines(self, cr, uid, move_line_ids, context=None):
        """
        Reconcile move lines lines, really. ERP core functionality.
        """
        reconcile_obj = self.pool.get('account.move.reconcile')
        account_move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        lines = account_move_line_obj.browse(cr, uid, move_line_ids,
                                                      context=context)

        for line in lines[1:]:
            if line.account_id != lines[0].account_id:
                raise orm.except_orm(
                    _('Error'),
                    _('Cannot reconcile between different accounts'))

        if any([line.reconcile_id and line.reconcile_id.line_id
                for line in lines]):
            raise orm.except_orm(
                _('Error'),
                _('Line is already fully reconciled'))

        currency = lines[0].company_id.currency_id

        partials = []
        line_ids = []
        for line in lines:
            if line.id not in line_ids:
                line_ids.append(line.id)
            if line.reconcile_partial_id:
                partial_ids = [line.id for line in line.reconcile_partial_id.line_partial_ids]
                line_ids.extend(partial_ids)
                if line.reconcile_partial_id.id not in partials:
                    partials.append(line.reconcile_partial_id.id)
        total = account_move_line_obj.get_balance(cr, uid, line_ids)
        is_zero = currency_obj.is_zero(cr, uid, currency, total)

        vals = {
            'type': 'auto',
            'line_id': is_zero and [(6, 0, line_ids)] or [(6, 0, [])],
            'line_partial_ids': is_zero and [(6, 0, [])] or [(6, 0, line_ids)],
            }

        if partials:
            if len(partials) > 1:
                reconcile_obj.unlink(
                    cr, uid, partials[1:], context=context)
            reconcile_obj.write(
                cr, uid, partials[0],
                vals, context=context)
        else:
            reconcile_obj.create(
                cr, uid, vals, context=context)

        for line_id in line_ids:
            netsvc.LocalService("workflow").trg_trigger(
                uid, 'account.move.line', line_id, cr)
        return True

    def create_aggregate_order(self, cr, uid, ids, context=None):
        """
            Create aggregate lines
        """
        account_move_line_obj = self.pool.get('account.move.line')
        account_move_obj = self.pool.get('account.move')
        payment_order_obj = self.pool.get('payment.order')
        payment_order_line_obj = self.pool.get('payment.line')
        payment_order_ids = context.get('active_ids', [])
        if not payment_order_ids:
            raise orm.except_orm(
                _('Error'),
                _('Please select a payment order'))
        if len(payment_order_ids) > 1:
            raise orm.except_orm(
                _('Error'),
                _('This operation can only be performed on a single '
                  'payment order'))

        today = fields.date.context_today(self, cr, uid, context=context)
        order = payment_order_obj.browse(
            cr, uid, payment_order_ids[0], context=context)

        # Execute chained wizard
        if not order.aggregate:
            raise orm.except_orm(
                        _('Error'),
                        _('Field aggregage not checked')
                        )

        move_id = account_move_obj.create(cr, uid, {
                'journal_id': order.mode.transfer_journal_id.id,
                'ref': _('Aggregate Payment Order %s') % order.reference,
                }, context=context)

        for order_line in order.line_ids:
            counter_move_line_ids = []
            for line in order_line.move_ids:
                if line.reconcile_id:
                    raise orm.except_orm(
                        _('Error'),
                        _('Move line %s has already been paid/reconciled') %
                        line.name
                        )

                # TODO: take multicurrency into account?

                # create the move line on the transfer account
                vals = {
                    'name': _('Transit %s') % (
                        line.invoice and
                        line.invoice.number or
                        line.ref),
                    'move_id': move_id,
                    #'partner_id': order_line.partner_id and order_line.partner_id.id or False,
                    'account_id': order.mode.transfer_account_id.id,
                    'credit': line.amount_to_pay,
                    'debit': 0.0,
                    'date': today,
                    }
                counter_move_line_id = account_move_line_obj.create(
                    cr, uid, vals, context=context)
                counter_move_line_ids.append(counter_move_line_id)

                # create the debit move line on the receivable account
                vals.update({
                        'name': _('Reconciliation %s') % (
                            line.invoice and
                            line.invoice.number or
                            line.name),
                        'account_id': line.account_id.id,
                        'credit': 0.0,
                        'debit': line.amount_to_pay,
                        'partner_id': order_line.partner_id
                                    and order_line.partner_id.id or False,
                            })
                reconcile_move_line_id = account_move_line_obj.create(
                    cr, uid, vals, context=context)

                self.reconcile_lines(
                    cr, uid, [reconcile_move_line_id, line.id],
                    context=context)

            total = account_move_line_obj.get_balance(
                cr, uid, counter_move_line_ids)

            vals = {
                'name': _('Transit reconciliation'),
                'move_id': move_id,
                'account_id': order.mode.transfer_account_id.id,
                'partner_id': order_line.partner_id
                                        and
                                        order_line.partner_id.id
                                        or
                                        False,
                'debit': total < 0 and -total or 0.0,
                'credit': total >= 0 and total or 0.0,
                'date': today,
                }
            aggregate_move_line_id = account_move_line_obj.create(
                cr, uid, vals, context=context)

            self.reconcile_lines(
                cr, uid, counter_move_line_ids + [aggregate_move_line_id],
                context=context)

            # create the credit move line on the aggregate partner
            vals.update({
                    'name': _('Amount payable'),
                    'account_id': order_line.partner_id.property_account_payable.id,
                    'partner_id': order_line.partner_id.id,
                    'debit': total >= 0 and total or 0.0,
                    'credit': total < 0 and -total or 0.0,
                    'partner_id': order_line.partner_id
                                        and
                                        order_line.partner_id.id
                                        or
                                        False,
                    })

            payable_move_line = account_move_line_obj.browse(
                cr, uid,
                account_move_line_obj.create(
                    cr, uid, vals, context=context),
                context=context)

            account_move_obj.post(cr, uid, [move_id], context=context)
            # Update transit move line id
            payment_order_line_obj.write(cr, uid, [order_line.id],{
                                'move_line_id': payable_move_line.id,
                                #'transit_move_line_id': payable_move_line.id,
                                }, context=context)

        wf_service = netsvc.LocalService('workflow')
        # The following workflow will be triggered by chained wizard
        #wf_service.trg_validate(uid, 'payment.order', order.id, 'sent', cr)

        # Execute the chained wizard set in payment mode
        return self.launch_chained_wizard(cr, uid, [order.id], context)

    # Copied from account_banking_export_payment/model/account_payment.py
    def launch_chained_wizard(self, cr, uid, ids, context=None):
        """
        Search for a wizard to launch according to the type.
        If type is manual. just confirm the order.
        """
        if context is None:
            context = {}
        result = {}
        payment_obj = self.pool.get('payment.order')
        orders = payment_obj.browse(cr, uid, ids, context)
        order = orders[0]
        # check if a wizard is defined for the chained order
        if order.mode.type and order.mode.chained_ir_model_id:
            context['active_ids'] = ids
            wizard_model = order.mode.chained_ir_model_id.model
            wizard_obj = self.pool.get(wizard_model)
            wizard_id = wizard_obj.create(cr, uid, {}, context)
            result = {
                'name': wizard_obj._description or _('Payment Order Export'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': wizard_model,
                'domain': [],
                'context': context,
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id': wizard_id,
                'nodestroy': True,
            }
        else:
            # process manual payments
            wf_service = netsvc.LocalService('workflow')
            for order_id in ids:
                wf_service.trg_validate(
                    uid, 'payment.order', order_id, 'done', cr
                )

        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
