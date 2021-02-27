# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest
import time
import tornado.ioloop

from decimal import Decimal
from valutakrambod.services import Service

class Gemini(Service):
    """
Query the Gemini API.

https://gemini.com/
https://docs.gemini.com/

"""
    baseurl = "https://api.gemini.com/v1/"

    def servicename(self):
        return "Gemini"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ]
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            url = "%spubticker/%s" % (self.baseurl, ("%s%s" % p).lower())
            #print(url)
            j, r = await self._jsonget(url)
            #print(j)
            self.updateRates(p,
                             Decimal(j['ask']),
                             Decimal(j['bid']),
                             j['volume']['timestamp'] / 1000)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Gemini websocket support not implemented 2018-09-28."""
        return None

class TestGemini(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Gemini()
        self.ioloop = tornado.ioloop.IOLoop.current()
    def checkTimeout(self):
        print("check timed out")
        self.ioloop.stop()
    def runCheck(self, check, timeout=30):
        to = self.ioloop.call_later(timeout, self.checkTimeout)
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
            self.assertTrue(spread > 0 and spread < 5)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)

    def checkUpdates(self):
        def registerUpdate(service, pair, changed):
            if False:
                print(pair,
                      service.rates[pair]['ask'],
                      service.rates[pair]['bid'],
                      time.time() - service.rates[pair]['when'],
                      time.time() - service.rates[pair]['stored'],
                )
            self.updates += 1
            self.ioloop.stop()
        self.s.subscribe(registerUpdate)
        self.s.periodicUpdate(3)
    def testUpdates(self):
        self.updates = 0
        self.runCheck(self.checkUpdates, timeout=10)
        self.assertTrue(0 < self.updates)

if __name__ == '__main__':
    t = TestGemini()
    unittest.main()
