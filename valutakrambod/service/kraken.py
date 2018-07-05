# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import time
import unittest

from valutakrambod.services import Orderbook
from valutakrambod.services import Service

class Kraken(Service):
    """
Query the Kraken API.  Documentation is available from
https://www.kraken.com/help/api#general-usage .
"""
    keymap = {
        'BTC' : 'XBT',
        }
    baseurl = "https://api.kraken.com/0/public/"
    def servicename(self):
        return "Kraken"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ('BTC', 'EUR'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    def _makepair(self, f, t):
        return "X%sZ%s" % (self._currencyMap(f), self._currencyMap(t))
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        self._fetchTicker(pairs)
        self._fetchOrderbooks(pairs)

    def _fetchOrderbooks(self, pairs):
        now = time.time()
        res = {}
        for pair in pairs:
            pairstr = self._makepair(pair[0], pair[1])
            o = Orderbook()
            url = "%sDepth?pair=%s" % (self.baseurl, pairstr)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                # For some strange reason, some orders have timestamps
                # in the future.  This is reported to Kraken Support
                # as request 1796106.
                for order in j['result'][pairstr][side]:
                    #print("Updating %s", (side, order), now - order[2])
                    o.update(oside, float(order[0]), float(order[1]))
                #print(o)
            self.updateOrderbook(pair, o)

    def _fetchTicker(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair= self._makepair(f, t)
            #print(pair)
            url = "%sTicker?pair=%s" % (self.baseurl, pair)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            if 0 != len(j['error']):
                raise Error(j['error'])
            ask = float(j['result'][pair]['a'][0])
            bid = float(j['result'][pair]['b'][0])
            self.updateRates(p, ask, bid, None)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Kraken do not provide websocket API 2018-06-27."""
        return None

class TestKraken(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Kraken()
    def testFetchTicker(self):
        res = self.s._fetchTicker()
        pair = ('BTC', 'EUR')
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
    t = TestKraken()
    unittest.main()
