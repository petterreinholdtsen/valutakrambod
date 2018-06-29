# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Coinbase(Service):
    baseurl = "https://api.coinbase.com/v2/"
    def servicename(self):
        return "Coinbase"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ]
    
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            sellurl = "%sprices/sell?currency=%s" % (self.baseurl, t)
            buyurl  = "%sprices/buy?currency=%s"  % (self.baseurl, t)
            (sj, sr) = self._jsonget(sellurl)
            #print(sj)
            (bj, br) = self._jsonget(buyurl)
            #print(bj)
            ask = float(bj['data']['amount'])
            bid = float(sj['data']['amount'])
            self.updateRates(p, ask, bid, None)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Coinbase do not provide websocket API 2018-06-27."""
        return None

def main():
    """
Run simple self test.
"""
    s = Coinbase()
    print(s.currentRates())

if __name__ == '__main__':
    main()
