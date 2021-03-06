# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 credativ Ltd (<http://credativ.co.uk>).
#    All Rights Reserved
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

{
        'name' : 'Product Image Batch Uploader',
        'version' : '0.1',
        'author' : 'credativ Ltd',
        'description' : """
This module adds a wizard which allows users to upload  a zipped batch of product images.
The zip file must include image files whose names match the corresponding product's SKU ('default_code'), not including the filetype extension.
        """,
        'website' : 'http://credativ.co.uk',
        'depends' : [
            'product',
            ],
        'init_xml' : [
            ],
        'update_xml' : [
            'wizard/uploader_view.xml',
            ],
        'css':['static/src/css/field_binary_css.css',],
        'installable' : True,
        'active' : False,
}
