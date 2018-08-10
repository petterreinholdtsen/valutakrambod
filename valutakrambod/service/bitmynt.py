# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest
import time
import tornado.ioloop

from decimal import Decimal
from valutakrambod.services import Service

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
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%sticker.pl" % self.baseurl
        #print(url)
        j, r = await self._jsonget(url)
        #print(j)
        res = {}
        for p in pairs:
            t = p[1].lower()
            if t in j:
                self.updateRates(p,
                                 Decimal(j[t]['sell']), # ask
                                 Decimal(j[t]['buy']), # bid
                                 j['timestamp'])
                res[p] = self.rates[p]
        return res

    def websocket(self):
        """Bitmynt do not provide websocket API 2018-06-27."""
        return None

class TestBitmynt(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Bitmynt()
        self.ioloop = tornado.ioloop.IOLoop.current()
    def checkTimeout(self):
        print("check timed out")
        self.ioloop.stop()
    def runCheck(self, check):
        to = self.ioloop.call_later(30, self.checkTimeout)
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

    def testUpdates(self):
        def printUpdate(service, pair, changed):
            print(pair,
                  service.rates[pair]['ask'],
                  service.rates[pair]['bid'],
                  time.time() - service.rates[pair]['when'],
                  time.time() - service.rates[pair]['stored'],
            )
            self.ioloop.stop()
        self.s.subscribe(printUpdate)
        self.s.periodicUpdate(3)
        #ioloop = tornado.ioloop.IOLoop.current()
        to = self.ioloop.call_later(10, self.ioloop.stop)
        self.ioloop.start()
        self.ioloop.remove_timeout(to)

if __name__ == '__main__':
    t = TestBitmynt()
    unittest.main()
