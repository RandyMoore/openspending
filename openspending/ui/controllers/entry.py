import logging

from pylons import request, response, tmpl_context as c
from pylons.controllers.util import abort, redirect
from pylons.i18n import _

from openspending.ui.lib.base import BaseController
from openspending.ui.lib.views import handle_request
from openspending.ui.lib.hypermedia import entry_apply_links
from openspending.lib.csvexport import write_csv
from openspending.lib.jsonexport import to_jsonp
from openspending.ui.lib import helpers as h
from openspending.ui.alttemplates import templating

log = logging.getLogger(__name__)


class EntryController(BaseController):

    def index(self, dataset, format='html'):
        self._get_dataset(dataset)

        if format in ['json', 'csv']:
            return redirect(h.url_for(controller='api/version2', action='search',
                format=format, dataset=dataset,
                **request.params))

        handle_request(request, c, c.dataset)
        return templating.render('entry/index.html')

    def view(self, dataset, id, format='html'):
        """
        Get a specific entry in the dataset, identified by the id. Entry
        can be return as html (default), json or csv.
        """

        # Generate the dataset
        self._get_dataset(dataset)
        # Get the entry that matches the given id. c.dataset.entries is 
        # a generator so we create a list from it's responses based on the
        # given constraint
        entries = list(c.dataset.entries(c.dataset.alias.c.id == id))
        # Since we're trying to get a single entry the list should only 
        # contain one entry, if not then we return an error
        if not len(entries) == 1:
            abort(404, _('Sorry, there is no entry %r') % id)
        # Add urls to the dataset and assign assign it as a context variable
        c.entry = entry_apply_links(dataset, entries.pop())

        # Get and set some context variables from the entry
        # This shouldn't really be necessary but it's here so nothing gets
        # broken
        c.id = c.entry.get('id')
        c.from_ = c.entry.get('from')
        c.to = c.entry.get('to')
        c.currency = c.entry.get('currency', c.dataset.currency).upper()
        c.time = c.entry.get('time')

        # Get the amount for the entry
        amount = c.entry.get('amount')
        # We adjust for inflation if the user as asked for this to be inflated
        if request.params.has_key('inflate'):
            try:
                # Inflate the amount. Target date is provided in request.params
                # as value for inflate and reference date is the date of the
                # entry. We also provide a list of the territories to extract
                # a single country for which to do the inflation
                c.inflation = h.inflate(amount, request.params['inflate'],
                                        c.time, c.dataset.territories)

                # The amount to show should be the inflated amount
                # and overwrite the entry's amount as well
                c.amount = c.inflation['inflated']
                c.entry['amount'] = c.inflation['inflated']

                # We include the inflation response in the entry's dict
                # HTML description assumes every dict value for the entry
                # includes a label so we include a default "Inflation
                # adjustment" for it to work.
                c.inflation['label'] = 'Inflation adjustment'
                c.entry['inflation_adjustment'] = c.inflation
            except:
                # If anything goes wrong in the try clause (and there's a lot
                # that can go wrong). We just say that we can't adjust for
                # inflation and set the context amount as the original amount
                h.flash_notice(_('Unable to adjust for inflation'))
                c.amount = amount
        else:
            # If we haven't been asked to inflate then we just use the
            # original amount
            c.amount = amount

        # Add custom html for the dataset entry if the dataset has some
        # custom html
        # 2013-11-17 disabled this as part of removal of genshi as depended on
        # a genshi specific helper.
        # TODO: reinstate if important
        # c.custom_html = h.render_entry_custom_html(c.dataset, c.entry)

        # Add the rest of the dimensions relating to this entry into a
        # extras dictionary. We first need to exclude all dimensions that
        # are already shown and then we can loop through the dimensions
        excluded_keys = ('time', 'amount', 'currency', 'from',
                         'to', 'dataset', 'id', 'name', 'description')

        c.extras = {}
        if c.dataset:
            # Create a dictionary of the dataset dimensions
            c.desc = dict([(d.name, d) for d in c.dataset.dimensions])
            # Loop through dimensions of the entry
            for key in c.entry:
                # Entry dimension must be a dataset dimension and not in
                # the predefined excluded keys
                if key in c.desc and \
                        not key in excluded_keys:
                    c.extras[key] = c.entry[key]

        # Return entry based on 
        if format == 'json':
            return to_jsonp(c.entry)
        elif format == 'csv':
            return write_csv([c.entry], response)
        else:
            return templating.render('entry/view.html')

    def search(self):
        c.content_section = 'search'
        return templating.render('entry/search.html')

