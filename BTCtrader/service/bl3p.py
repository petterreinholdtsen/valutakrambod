# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Bl3p(Service):
    baseurl = "https://api.bl3p.eu/1/"
    def servicename(self):
        return "Bl3p"

    def ratepairs(self):
        return [
            ('LTC', 'EUR'),
            ('BTC', 'EUR'),
            ]
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = []
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%s%s/ticker" % (self.baseurl, pair)
            #print url
            (j, r) = self._jsonget(url)
            #print(r.code)
            if 200 != r.code:
                raise Error()
            #print(j)
            ask = j['ask']
            bid = j['bid']
            res.append({
                'from': f,
                'to': t,
                'ask': ask,
                'bid': bid,
                'when': j['timestamp']
            })
        return res

def main():
    """
Run simple self test.
"""
    s = Bl3p()
    print(s.currentRates())

if __name__ == '__main__':
    main()
