# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from valutakrambod.services import Service

class Bitmynt(Service):
    """
Query the Bitmynt API.
"""
    baseurl = "http://bitmynt.no/"

    def servicename(self):
        return "Bitmynt"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ]
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%sticker.pl" % self.baseurl
        #print(url)
        j, r = self._jsonget(url)
        #print(j)
        res = {}
        for p in pairs:
            t = p[1].lower()
            if t in j:
                self.updateRates(p,
                                 float(j[t]['sell']), # ask
                                 float(j[t]['buy']), # bid
                                 j['timestamp'])
                res[p] = self.rates[p]
        return res

    def websocket(self):
        """Bitmynt do not provide websocket API 2018-06-27."""
        return None

def main():
    """
Run simple self test.
"""
    s = Bitmynt()
    print(s.currentRates())

if __name__ == '__main__':
    main()
