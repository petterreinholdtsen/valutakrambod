# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import simplejson
import time
import tornado.ioloop
import unittest

from decimal import Decimal
from valutakrambod.services import Service

class BitcoinsNorway(Service):
    """
Query the Bitcoin Norway API.

https://bitcoinsnorway.com/apiref/

"""
    keymap = {
        'BTC' : 'XBT',
        # Pass others through unchanged
        }
    baseurl = "https://api.bitcoinsnorway.com:8413/ajax/v1"

    def servicename(self):
        return "BitcoinsNorway"
    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ('BTC', 'USD'),
            ('LTC', 'NOK'),
            ('LTC', 'EUR'),
            ('LTC', 'USD'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency

    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%s/GetTicker" % self.baseurl
        #print(url)
        res = {}
        for pair in pairs:
            pairstr = "%s%s" % (self._currencyMap(pair[0]),
                                self._currencyMap(pair[1]))
            body = {
                "productPair": pairstr,
            }
            c, r = await self._post(url, simplejson.dumps(body))
            j = simplejson.loads(c.decode('UTF-8'), use_decimal=True)
            #print(j)
            self.updateRates(pair,
                             Decimal(j['ask']),
                             Decimal(j['bid']),
                             None, # No timestamp provided
            )
            res[pair] = self.rates[pair]
        return res

    def websocket(self):
        """BitcoinsNorway websocket API not implemented 2018-08-26."""
        return None

class TestBitcoinsNorway(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = BitcoinsNorway()
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
            self.assertTrue(spread >= 0)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)

    def testUpdates(self):
        def printUpdate(service, pair, changed):
            print(pair,
                  service.rates[pair]['ask'],
                  service.rates[pair]['bid'],
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
    t = TestBitcoinsNorway()
    unittest.main()
