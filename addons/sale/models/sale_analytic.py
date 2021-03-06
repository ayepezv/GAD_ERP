# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def _compute_analytic(self, domain=None):
        lines = {}
        if not domain:
            # To filter on analyic lines linked to an expense
            domain = [('so_line', 'in', self.ids), ('amount', '<=', 0.0)]
        data = self.env['account.analytic.line'].read_group(
            domain,
            ['so_line', 'unit_amount', 'product_uom_id'], ['product_uom_id', 'so_line'], lazy=False
        )
        for d in data:
            if not d['product_uom_id']:
                continue
            line = self.browse(d['so_line'][0])
            lines.setdefault(line, 0.0)
            uom = self.env['product.uom'].browse(d['product_uom_id'][0])
            if line.product_uom.category_id == uom.category_id:
                qty = uom._compute_quantity(d['unit_amount'], line.product_uom)
            else:
                qty = d['unit_amount']
            lines[line] += qty

        for line, qty in lines.items():
            line.qty_delivered = qty
        return True


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"
    so_line = fields.Many2one('sale.order.line', string='Sale Order Line')

    def _get_invoice_price(self, order):
        if self.product_id.expense_policy == 'sales_price':
            return self.product_id.with_context(
                partner=order.partner_id.id,
                date_order=order.date_order,
                pricelist=order.pricelist_id.id,
                uom=self.product_uom_id.id
            ).price
        if self.unit_amount == 0.0:
            return 0.0
        price_unit = abs(self.amount / self.unit_amount)
        currency_id = self.currency_id or self.account_id.currency_id
        if currency_id and currency_id != order.currency_id:
            price_unit = currency_id.compute(price_unit, order.currency_id)
        return price_unit

    def _get_sale_order_line_vals(self, order, price):
        last_so_line = self.env['sale.order.line'].search([('order_id', '=', order.id)], order='sequence desc', limit=1)
        last_sequence = last_so_line.sequence + 1 if last_so_line else 100

        fpos = order.fiscal_position_id or order.partner_id.property_account_position_id
        taxes = fpos.map_tax(self.product_id.taxes_id, self.product_id, order.partner_id)

        return {
            'order_id': order.id,
            'name': self.name,
            'sequence': last_sequence,
            'price_unit': price,
            'tax_id': [x.id for x in taxes],
            'discount': 0.0,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom_id.id,
            'product_uom_qty': 0.0,
            'qty_delivered': self.unit_amount,
        }

    def _get_sale_order_line(self, vals=None):
        result = dict(vals or {})
        so_line = result.get('so_line', False) or self.so_line
        if not so_line and self.account_id and self.product_id and (self.product_id.expense_policy != 'no'):
            order = self.env['sale.order'].search([('project_id', '=', self.account_id.id), ('state', '=', 'sale')], limit=1)
            if not order:
                return result
            price = self._get_invoice_price(order)
            so_lines = self.env['sale.order.line'].search([
                ('order_id', '=', order.id),
                ('price_unit', '=', price),
                ('product_id', '=', self.product_id.id)])

            if so_lines:
                result.update({'so_line': so_lines[0].id})
            else:
                order_line_vals = self._get_sale_order_line_vals(order, price)
                if order_line_vals:
                    so_line = self.env['sale.order.line'].create(order_line_vals)
                    so_line._compute_tax_id()
                    result.update({'so_line': so_line.id})
        return result

    @api.multi
    def write(self, values):
        if self._context.get('create', False):
            return super(AccountAnalyticLine, self).write(values)

        lines = super(AccountAnalyticLine, self).write(values)
        for line in self:
            res = line.sudo()._get_sale_order_line(vals=values)
            super(AccountAnalyticLine, line).write(res)

        self.mapped('so_line').sudo()._compute_analytic()
        return lines

    @api.model
    def create(self, values):
        line = super(AccountAnalyticLine, self).create(values)
        res = line.sudo()._get_sale_order_line(vals=values)
        line.with_context(create=True).write(res)
        line.mapped('so_line').sudo()._compute_analytic()
        return line
