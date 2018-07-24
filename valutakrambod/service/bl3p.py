# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import decimal
import simplejson
import time
import tornado.ioloop
import unittest
import urllib

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.websocket import WebSocketClient

class Bl3p(Service):
    """
Query the Bl3p API.  Documentation is available from
https://bl3p.eu/api .
"""
    baseurl = "https://api.bl3p.eu/1/"
    def servicename(self):
        return "Bl3p"

    def ratepairs(self):
        return [
            ('LTC', 'EUR'),
            ('BTC', 'EUR'),
            ]

    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%s%s/ticker" % (self.baseurl, pair)
            #print url
            (j, r) = await self._jsonget(url)
            #print(r.code)
            if 200 != r.code:
                raise Error()
            #print(j)
            ask = decimal.Decimal(j['ask'])
            bid = decimal.Decimal(j['bid'])
            self.updateRates(p, ask, bid, int(j['timestamp']))
            res[p] = self.rates[p]
        return res

    class WSClient(WebSocketClient):
        def __init__(self, service):
            super().__init__(service)
            self.url = "wss://api.bl3p.eu/1/BTCEUR/orderbook"
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            pass
        def _on_message(self, msg):
            m = simplejson.loads(msg, use_decimal=True)
            #print(m)
            o = Orderbook()
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for e in m[side]:
                    o.update(oside, decimal.Decimal(e['price_int']) / 100000,
                             decimal.Decimal(e['price_int']) / 100000 )
            # FIXME setting our own timestamp, as there is no
            # timestamp from the source.  Asked bl3p to set one in
            # email sent 2018-06-27.
            #o.setupdated(time.time())
            pair = (m['marketplace'][:3], m['marketplace'][3:])
            self.service.updateOrderbook(pair, o)
        def _on_connection_close(self):
            pass
        def _on_connection_error(self, exception):
            pass
    def websocket(self):
        return self.WSClient(self)

class TestBl3p(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Bl3p()
        self.ioloop = tornado.ioloop.IOLoop.current()
    def runCheck(self, check):
        to = self.ioloop.call_later(10, self.ioloop.stop) # Add timeout
        self.ioloop.add_callback(check)
        self.ioloop.start()
        self.ioloop.remove_timeout(to)
    async def checkCurrentRates(self):
        res = await self.s.currentRates()
        pair = ('BTC', 'EUR')
        self.assertTrue(pair in res)
        ask = res[pair]['ask']
        bid = res[pair]['bid']
        self.assertTrue(ask >= bid)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)
    def testWebsocket(self):
        """Test websocket subscription of updates.

        """
        def printUpdate(service, pair, changed):
            print(pair,
                  service.rates[pair]['ask'],
                  service.rates[pair]['bid'],
                  time.time() - service.rates[pair]['stored'] ,
            )
            self.ioloop.stop()
        self.s.subscribe(printUpdate)
        c = self.s.websocket()
        c.connect()
        self.ioloop.call_later(10, self.ioloop.stop)
        self.ioloop.start()

if __name__ == '__main__':
    t = TestBl3p()
    unittest.main()
