# coding: utf-8
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SearchDuplicatesWizard(models.TransientModel):
    _name = 'search.duplicates.wizard'
    _description = 'Search Duplicates'
    _rec_name = 'model_id'

    model_id = fields.Many2one('ir.model', 'Model', required=True)
    field_id = fields.Many2one('ir.model.fields', 'Campo', required=True,
                               domain="[('model_id','=',model_id),"
                               "('ttype','not in',['binary','one2many',"
                               "'many2many']),('store','=',True),"
                               "('name','not in',['create_uid','write_uid',"
                               "'create_date','write_date','display_name',"
                               "'id','__last_update'])]")
    field_ids = fields.Many2many('ir.model.fields', string='Fields to export',
                                 domain="[('model_id','=',model_id),"
                                 "('ttype','not in',['binary','one2many',"
                                 "'many2many']),('store','=',True)]",
                                 help='Seleccione los campos a exportar en el '
                                 'CSV, si no se elige ningún campo, solo se '
                                 'tomará el ID y el name.')
    view_mode = fields.Selection([('csv', 'CSV'), ('list', 'Listado')],
                                 'Mode', default='csv')
    un_resultado = fields.Boolean(help='Solo mostrará un registro por cada repetido')

    @api.onchange('model_id')
    def onchange_model(self):
        self.field_id = False
        self.field_ids = False

    @api.multi
    def search_dupes(self):
        self.ensure_one()
        model = self.env[self.model_id.model]
        field = self.field_id.name
        query = """ SELECT {field}, COUNT(*)
                    FROM {table}
                    WHERE {field} IS NOT NULL
                    GROUP BY {field}
                    HAVING COUNT(*) > 1 """.format(field=field,
                                                   table=model._table)
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()
        if not rows:
            raise UserError(_(u'There are no duplicates'))
        results = ["'%s'" % row[field] for row in rows if row[field]]
        names = self.field_ids.mapped('name')
        query = """ SELECT id, {field}{sep}{fields}
                    FROM {table}
                    WHERE {field} IN ({res})
                    ORDER BY {field} """.format(field=field,
                                                sep=', ' if names else '',
                                                fields=', '.join(names),
                                                table=model._table,
                                                res=', '.join(results))
        self.env.cr.execute(query)
        rows = self.env.cr.dictfetchall()
        if self.un_resultado:
            temp_rows, rows = rows[:], []
            usados = []
            for row in temp_rows:
                if row[field] in usados:
                    continue
                usados.append(row[field])
                rows.append(row)

        if self.view_mode == 'list':
            ids = [row['id'] for row in rows]
            if not model.search([('id', 'in', ids)]):
                raise UserError(_(u' The list can not be displayeda, use CSV.'))
            return {
                'name': 'Duplicados',
                'type': 'ir.actions.act_window',
                'res_model': self.model_id.model,
                'domain': [('id', 'in', ids)],
                'view_mode': 'tree',
                'view_type': 'form'
            }
        names = names or ['id']
        data = u'%s' % u';'.join(names)
        for row in rows:
            data += u'\n%s' % u';'.join(unicode(row[attr]) for attr in names)

        data = base64.encodestring(data.encode('utf-8'))
        attach_vals = {
            'name': '%s.csv' % self.model_id.model,
            'datas': data,
            'datas_fname': '%s.csv' % self.model_id.model,
        }
        doc_id = self.env['ir.attachment'].create(attach_vals)
        return {
            'type': 'ir.actions.act_url',
            'url': 'web/content/?model=ir.attachment&id={id}&field=datas'
                   '&filename_field=datas_fname&download=true&filename={name}'
                   .format(id=doc_id.id, name=doc_id.name),
            'target': 'new',
        }
