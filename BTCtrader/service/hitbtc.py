# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Hitbtc(Service):
    """
Query the Hitbtc API.
"""
    baseurl = "http://api.hitbtc.com/api/1/"
    def servicename(self):
        return "Hitbtc"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = []
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%spublic/%s/ticker" % (self.baseurl, pair)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            ask = float(j['ask'])
            bid = float(j['bid'])
            res.append({
                'from': f,
                'to': t,
                'ask': ask,
                'bid': bid,
                'when': j['timestamp'] / 1000.0,
            })
        return res

def main():
    """
Run simple self test.
"""
    s = Hitbtc()
    print(s.currentRates())

if __name__ == '__main__':
    main()
