# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service


class Paymium(Service):
    """Query the Paymium API.  Documentation is available from
https://github.com/Paymium/api-documentation/#ticker

    """
    baseurl = "https://paymium.com/api/v1/data/"
    def servicename(self):
        return "Paymium"

    def ratepairs(self):
        return [
            ('BTC', 'EUR'),
            ]
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="X%sZ%s" % (f, t)
            #print(pair)
            url = "%s%s/ticker" % (self.baseurl, t.lower())
            (j, r) = self._jsonget(url)
            #print(r.code)
            if 200 != r.code:
                raise Error()
            #print(j)
            ask = j['ask']
            bid = j['bid']
            self.updateRates(p, ask, bid, j['at'])
            res[p] = self.rates[p]
        return res

def main():
    """
Run simple self test.
"""
    s = Paymium()
    print(s.currentRates())

if __name__ == '__main__':
    main()
