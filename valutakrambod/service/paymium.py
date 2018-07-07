# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import time
import unittest

from valutakrambod.services import Service
from valutakrambod.services import Orderbook


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
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        #self._fetchTicker(pairs)
        self._fetchOrderbooks(pairs)

    def _fetchOrderbooks(self, pairs):
        now = time.time()
        for pair in pairs:
            f = pair[0]
            t = pair[1]
            url = "%s%s/depth" % (self.baseurl, t.lower())
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            o = Orderbook()
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for order in j[side]:
                    if t != order['currency']: # sanity check
                        raise Exception("unexpected currency returned by depth call")
                    #print("Updating %s", (side, order), now - order['timestamp'])
                    o.update(oside,
                             order['price'],
                             order['amount'],
                             order['timestamp'])
                #print(o)
            self.updateOrderbook(pair, o)

    def _fetchTicker(self, pairs = None):
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

class TestPaymium(unittest.TestCase):
    """
Run simple self test of the Paymium service class.
"""
    def setUp(self):
        self.s = Paymium()

    def testFetchTicker(self):
        res = self.s._fetchTicker()
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)

    def testFetchOrderbooks(self):
        pairs = self.s.ratepairs()
        self.s._fetchOrderbooks(pairs)
        for pair in pairs:
            self.assertTrue(pair in self.s.rates)
            self.assertTrue(pair in self.s.orderbooks)
            ask = self.s.rates[pair]['ask']
            bid = self.s.rates[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            self.assertTrue(spread > 0 and spread < 5)

if __name__ == '__main__':
    t = TestPaymium()
    unittest.main()
