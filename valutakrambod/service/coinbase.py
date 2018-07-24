# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest
import tornado.ioloop

from decimal import Decimal
from valutakrambod.services import Service

class Coinbase(Service):
    baseurl = "https://api.coinbase.com/v2/"
    def servicename(self):
        return "Coinbase"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ('BTC', 'USD'),
            ]
    
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            sellurl = "%sprices/sell?currency=%s" % (self.baseurl, t)
            buyurl  = "%sprices/buy?currency=%s"  % (self.baseurl, t)
            (sj, sr) = await self._jsonget(sellurl)
            #print(sj)
            (bj, br) = await self._jsonget(buyurl)
            #print(bj)
            ask = Decimal(bj['data']['amount'])
            bid = Decimal(sj['data']['amount'])
            self.updateRates(p, ask, bid, None)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Coinbase do not provide websocket API 2018-06-27."""
        return None

class TestCoinbase(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Coinbase()
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
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)

if __name__ == '__main__':
    t = TestCoinbase()
    unittest.main()
