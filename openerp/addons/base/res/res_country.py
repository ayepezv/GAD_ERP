# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import logging
from odoo import api, fields, models
from psycopg2 import IntegrityError
from odoo.tools.translate import _
_logger = logging.getLogger(__name__)


@api.model
def location_name_search(self, name='', args=None, operator='ilike', limit=100):
    if args is None:
        args = []

    records = self.browse()
    if len(name) == 2:
        records = self.search([('code', 'ilike', name)] + args, limit=limit)

    search_domain = [('name', operator, name)]
    if records:
        search_domain.append(('id', 'not in', records.ids))
    records += self.search(search_domain + args, limit=limit)

    # the field 'display_name' calls name_get() to get its value
    return [(record.id, record.display_name) for record in records]


class Country(models.Model):
    _name = 'res.country'
    _description = 'Country'
    _order = 'name'

    name = fields.Char(string='Country Name', required=True, translate=True, help='The full name of the country.')
    code = fields.Char(string='Country Code', size=2,
                help='The ISO country code in two chars. \nYou can use this field for quick search.')
    address_format = fields.Text(help="""You can state here the usual format to use for the \
addresses belonging to this country.\n\nYou can use the python-style string patern with all the field of the address \
(for example, use '%(street)s' to display the field 'street') plus
            \n%(state_name)s: the name of the state
            \n%(state_code)s: the code of the state
            \n%(country_name)s: the name of the country
            \n%(country_code)s: the code of the country""",
            default='%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s')
    currency_id = fields.Many2one('res.currency', string='Currency')
    image = fields.Binary(attachment=True)
    phone_code = fields.Integer(string='Country Calling Code')
    country_group_ids = fields.Many2many('res.country.group', 'res_country_res_country_group_rel',
                         'res_country_id', 'res_country_group_id', string='Country Groups')
    state_ids = fields.One2many('res.country.state', 'country_id', string='States')

    _sql_constraints = [
        ('name_uniq', 'unique (name)',
            'The name of the country must be unique !'),
        ('code_uniq', 'unique (code)',
            'The code of the country must be unique !')
    ]

    name_search = location_name_search

    @api.model
    def create(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].upper()
        return super(Country, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].upper()
        return super(Country, self).write(vals)

    @api.multi
    def get_address_fields(self):
        self.ensure_one()
        return re.findall(r'\((.+?)\)', self.address_format)


class CountryGroup(models.Model):
    _description = "Country Group"
    _name = 'res.country.group'

    name = fields.Char(required=True)
    country_ids = fields.Many2many('res.country', 'res_country_res_country_group_rel',
                                   'res_country_group_id', 'res_country_id', string='Countries')


class CountryState(models.Model):
    _description = "Country state"
    _name = 'res.country.state'
    _order = 'code'

    country_id = fields.Many2one('res.country', string='Country', required=True)
    name = fields.Char(string='State Name', required=True,
               help='Administrative divisions of a country. E.g. Fed. State, Departement, Canton')
    code = fields.Char(string='State Code', help='The state code.', required=True)

    name_search = location_name_search

    @api.model
    def merge_states(self):
        IMD = self.env['ir.model.data']

        query = """
            SELECT st.id, st.oldid, imd.id, imd.name, imd2.id, ids
            FROM (
                SELECT st.country_id, st.code, max(st.id) as id, min(st.id) as oldid, string_agg(cast(id as text), ',') as ids
                FROM res_country_state st
                GROUP BY st.country_id, st.code
                HAVING count(*) > 1
            ) st
                LEFT JOIN ir_model_data imd on (imd.model = 'res.country.state' and imd.res_id = st.id)
                LEFT JOIN ir_model_data imd2 on (imd2.model = 'res.country.state' and imd2.res_id = st.oldid)
            WHERE imd.module = 'base';
        """
        self._cr.execute(query)
        data = self._cr.fetchall()

        for st_id, st_oldid, imd_id, imd_name, imd2_id, ids in data:
            values = dict(module=self._module)
            if imd2_id:
                # If duplicated record had already a xml_id we update the old xml_id and
                # force to delete the new xml_id created to avoid constraint error
                keepid = imd2_id
                IMD.browse(imd_id).unlink()
                values.update(name=imd_name)
            else:
                # Else we point the new xml_id to the oldest duplicated state
                keepid = imd_id
                values.update(res_id=st_oldid)

            IMD.browse(keepid).write(values)
            self.browse(st_id).unlink()

            duplicated_ids = set(map(int, ids.split(','))) - set([st_id, st_oldid])
            if duplicated_ids:
                _logger.warning(_('State with id [%s] (%s) seems to have duplicated code: %s' % (st_oldid, imd_name, ','.join(duplicated_ids))))

        if data:
            self._add_sql_constraints()

    _sql_constraints = [
        ('name_code_uniq', 'unique(country_id, code)', 'The code of the state must be unique by country !')
    ]
