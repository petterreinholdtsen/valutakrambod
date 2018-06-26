# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

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
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%sticker.pl" % self.baseurl
        #print(url)
        j, r = self._jsonget(url)
        #print(j)
        res = []
        for p in pairs:
            #print(pair)
            f = p[0]
            t = p[1]
            ask = float(j[t.lower()]['sell'])
            bid = float(j[t.lower()]['buy'])
            res.append({
                'from': f,
                'to': t,
                'ask': ask,
                'bid': bid,
                # FIXME convert timestamp
                'when': j['time'],
            })
        return res

def main():
    """
Run simple self test.
"""
    s = Bitmynt()
    print(s.currentRates())

if __name__ == '__main__':
    main()
