# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import unittest
import time

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
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%sticker.pl" % self.baseurl
        #print(url)
        j, r = self._jsonget(url)
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
    def testCurrentRates(self):
        res = self.s.currentRates()
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            self.assertTrue(spread > 0 and spread < 5)
    def testUpdates(self):
        from tornado import ioloop
        def printUpdate(service, pair, changed):
            print(pair,
                  service.rates[pair]['ask'],
                  service.rates[pair]['bid'],
                  time.time() - service.rates[pair]['when'],
                  time.time() - service.rates[pair]['stored'],
            )
        self.s.subscribe(printUpdate)
        self.s.periodicUpdate(3)
        io_loop = ioloop.IOLoop.instance()
        io_loop.call_later(10, io_loop.stop)
        io_loop.start()

if __name__ == '__main__':
    t = TestBitmynt()
    unittest.main()
