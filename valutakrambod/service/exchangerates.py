# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import dateutil

from valutakrambod.services import Service

class Exchangerates(Service):
    """Query the Exchange rates API. Documentation is available from
https://exchangeratesapi.io/ .  The rates are updated 16:00 CET
according to
https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

    """
    baseurl = "https://exchangeratesapi.io/api/"

    def servicename(self):
        return "Exchangerates"

    def ratepairs(self):
        return [
            ('EUR', 'NOK'),
            ('EUR', 'USD'),
            ]
    def datestr2epoch(self, datestr):
        when = dateutil.parser.parse(datestr)
        return when.timestamp()
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%slatest" % self.baseurl
        j, r = self._jsonget(url)
        base = j['base']
        res = {}
        for r in j['rates'].keys():
            p = (base, r)
            #print(p)
            if p not in self.ratepairs():
                continue
            when = self.datestr2epoch(j['date'] + 'T16:00CET')
            self.updateRates(p,
                             j['rates'][r],
                             j['rates'][r],
                             when)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Exchange rates do not provide websocket API 2018-06-27."""
        return None

def main():
    """
Run simple self test.
"""
    s = Exchangerates()
    print(s.currentRates())

if __name__ == '__main__':
    main()
