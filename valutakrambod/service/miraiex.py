# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest

from valutakrambod.services import Orderbook
from valutakrambod.services import Service

class MiraiEx(Service):
    """Query the Mirai Exchange API.  Based on documentation found in
https://gist.github.com/mikalv/7b4f44a34fd48e0b87877c1771903b0a/ .

    """
    baseurl = "http://miraiex.com/api/v1/"

    def servicename(self):
        return "MiraiEx"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('ANC', 'BTC'),
            ('GST', 'BTC'),
            ('LTC', 'BTC'),
            ]
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        #self.fetchMarkets(pairs)
        self.fetchOrderbooks(pairs)

    def fetchOrderbooks(self, pairs):
        for pair in pairs:
            o = Orderbook()
            url = "%smarkets/%s%s/depth" % (self.baseurl, pair[0], pair[1])
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for order in j[side]:
                    #print("Updating %s for %s", (side, pair), order)
                    o.update(oside, float(order[0]), float(order[1]))
                #print(o)
            self.updateOrderbook(pair, o)

    def fetchMarkets(self, pairs):
        url = "%smarkets" % self.baseurl
        #print(url)
        j, r = self._jsonget(url)
        #print(j)
        res = {}
        for market in j:
            pair = (market['id'][:3], market['id'][3:])
            ask = bid = float('nan')
            if 'ask' in market and market['ask'] is not None:
                ask = float(market['ask'])
            if 'bid' in market and market['bid'] is not None:
                bid = float(market['bid'])
            #print(pair)
            if pair in pairs:
                self.updateRates(pair,
                                 ask,
                                 bid,
                                 None)
                res[pair] = self.rates[pair]
        return res

    def websocket(self):
        """Not known of Mirai provide websocket API 2018-07-02."""
        return None

class TestMiraiEx(unittest.TestCase):
    """Simple self test.

    """
    def testCompareOrderbookTicker(self):
        # Try to detect when the two ways to fetch the ticker disagree
        asks = {}
        bids = {}
        #print(self.s.fetchOrderbooks(self.s.wantedpairs))
        for pair in self.s.wantedpairs:
            asks[pair] = self.s.rates[pair]['ask']
            bids[pair] = self.s.rates[pair]['bid']
        #print(self.s.fetchRates(self.s.wantedpairs))
        for pair in self.s.wantedpairs:
            if asks[pair] != self.s.rates[pair]['ask']:
                print("ask order book (%.1f and ticker (%.1f) differ for %s" % (
                    asks[pair],
                    self.s.rates[pair]['ask'],
                    pair
                ))
                self.assertTrue(False)
            if bids[pair] != self.s.rates[pair]['bid']:
                print("bid order book (%.1f and ticker (%.1f) differ for %s" % (
                    bids[pair],
                    self.s.rates[pair]['bid'],
                    pair
                ))
                self.assertTrue(False)
    def setUp(self):
        self.s = MiraiEx()
        self.s.currentRates()
    def testConnection(self):
        for pair in self.s.wantedpairs:
            self.assertTrue(pair in self.s.rates)

if __name__ == '__main__':
    t = TestMiraiEx()
    unittest.main()
