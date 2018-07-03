# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.


import dateutil
import datetime

from pytz import UTC

from valutakrambod.services import Service

class OneForge(Service):
    """Query the 1 Forge API. Documentation is available from
https://1forge.com/forex-data-api .

    """
    baseurl = "https://forex.1forge.com/1.0.1/"

    def servicename(self):
        return "OneForge"

    def ratepairs(self):
        return [
            ('EUR', 'NOK'),
            ('USD', 'EUR'),
            ('USD', 'NOK'),
            ]
    def setAPIkey(self, apikey):
        self.apikey = apikey
    def fetchRates(self, pairs = None):
        if not hasattr(self, 'apikey'):
            raise Exception('1Forge require API key')
        if pairs is None:
            pairs = self.ratepairs()
        #print(pairs)
        pairstr = ','.join(map(lambda t: "%s%s" % (t[0], t[1]), pairs))
        url = "%squotes?pairs=%s&api_key=%s" % (self.baseurl, pairstr, self.apikey)
        #print(url)
        j, r = self._jsonget(url)
        #print(j)
        res = {}
        for r in j:
            pair = (r['symbol'][:3], r['symbol'][3:])
            if pair not in self.ratepairs():
                continue
            self.updateRates(pair,
                             r['ask'],
                             r['bid'],
                             r['timestamp'],
            )
            res[pair] = self.rates[pair]
        return res

    def websocket(self):
        """Websocket API not yet implemented 2018-07-03."""
        return None

def main():
    """
Run simple self test.
"""
    s = OneForge()
    print(s.currentRates())

if __name__ == '__main__':
    main()
