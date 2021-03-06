# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class WebsiteConfigSettings(models.TransientModel):

    _name = 'website.config.settings'
    _inherit = 'res.config.settings'

    def _default_website(self):
        return self.env['website'].search([], limit=1)

    website_id = fields.Many2one('website', string="website", default=_default_website, required=True)
    website_name = fields.Char('Website Name', related='website_id.name')

    language_ids = fields.Many2many(related='website_id.language_ids', relation='res.lang')
    default_lang_id = fields.Many2one(related='website_id.default_lang_id', relation='res.lang')
    default_lang_code = fields.Char('Default language code', related='website_id.default_lang_code')
    google_analytics_key = fields.Char('Google Analytics Key', related='website_id.google_analytics_key')

    social_twitter = fields.Char(related='website_id.social_twitter')
    social_facebook = fields.Char(related='website_id.social_facebook')
    social_github = fields.Char(related='website_id.social_github')
    social_linkedin = fields.Char(related='website_id.social_linkedin')
    social_youtube = fields.Char(related='website_id.social_youtube')
    social_googleplus = fields.Char(related='website_id.social_googleplus')
    compress_html = fields.Boolean('Compress rendered HTML for a better Google PageSpeed result', related='website_id.compress_html')
    cdn_activated = fields.Boolean('Use a Content Delivery Network (CDN)', related='website_id.cdn_activated')
    cdn_url = fields.Char(related='website_id.cdn_url')
    cdn_filters = fields.Text(related='website_id.cdn_filters')
    module_website_form_editor = fields.Boolean("Form builde = create and customize forms")
    module_website_version = fields.Boolean("A/B testing and versioning")
    favicon = fields.Binary('Favicon', related='website_id.favicon')
