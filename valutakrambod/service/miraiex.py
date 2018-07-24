# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest
import tornado.ioloop

from decimal import Decimal

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
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.wantedpairs
        #await self.fetchMarkets(pairs)
        await self.fetchOrderbooks(pairs)

    async def fetchOrderbooks(self, pairs):
        for pair in pairs:
            o = Orderbook()
            url = "%smarkets/%s%s/depth" % (self.baseurl, pair[0], pair[1])
            #print(url)
            j, r = await self._jsonget(url)
            #print(j)
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for order in j[side]:
                    #print("Updating %s for %s" % (side, pair), order)
                    o.update(oside, Decimal(order[0]), Decimal(order[1]))
                #print(o)
            self.updateOrderbook(pair, o)

    async def fetchMarkets(self, pairs):
        url = "%smarkets" % self.baseurl
        #print(url)
        j, r = await self._jsonget(url)
        #print(j)
        res = {}
        for market in j:
            pair = (market['id'][:3], market['id'][3:])
            ask = bid = Decimal('nan')
            if 'ask' in market and market['ask'] is not None:
                ask = Decimal(market['ask'])
            if 'bid' in market and market['bid'] is not None:
                bid = Decimal(market['bid'])
            #print(pair)
            if pair in pairs:
                self.updateRates(pair,
                                 ask,
                                 bid,
                                 None)
                res[pair] = self.rates[pair]
        return res

    def websocket(self):
        """Not known if Mirai provide websocket API 2018-07-02."""
        return None

class TestMiraiEx(unittest.TestCase):
    """Simple self test.

    """
    def setUp(self):
        self.s = MiraiEx(['BTC', 'ANC', 'NOK', 'GST', 'LTC'])
        self.ioloop = tornado.ioloop.IOLoop.current()
    def runCheck(self, check):
        to = self.ioloop.call_later(10, self.ioloop.stop) # Add timeout
        self.ioloop.add_callback(check)
        self.ioloop.start()
        self.ioloop.remove_timeout(to)
    async def checkCurrentRates(self):
        res = await self.s.currentRates()
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            # Not checking spread, as some spreads are > 65 (ANC-BTC seen)
            #print("Spread for %s:" % str(pair), spread)
            #self.assertTrue(0 < spread and spread < 100)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)
    async def checkCompareOrderbookTicker(self):
        # Try to detect when the two ways to fetch the ticker disagree
        asks = {}
        bids = {}
        laststore = newstore = 0
        res = await self.s.fetchOrderbooks(self.s.wantedpairs)
        for pair in self.s.wantedpairs:
            asks[pair] = self.s.rates[pair]['ask']
            bids[pair] = self.s.rates[pair]['bid']
            if laststore < self.s.rates[pair]['stored']:
                laststore = self.s.rates[pair]['stored']
        res = await self.s.fetchRates(self.s.wantedpairs)
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
            if newstore < self.s.rates[pair]['stored']:
                newstore = self.s.rates[pair]['stored']
            #print(laststore, newstore)
            self.assertTrue(laststore != newstore)
        self.ioloop.stop()
    def testCompareOrderbookTicker(self):
        self.runCheck(self.checkCompareOrderbookTicker)

if __name__ == '__main__':
    t = TestMiraiEx()
    unittest.main()
