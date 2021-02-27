# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import configparser
import dateutil.parser
import simplejson
import time
import tornado.ioloop
import unittest

from os.path import expanduser

from decimal import Decimal

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.websocket import WebSocketClient

class Hitbtc(Service):
    """
Query the Hitbtc API.
"""
    baseurl = "http://api.hitbtc.com/api/1/"
    def servicename(self):
        return "Hitbtc"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%spublic/%s/ticker" % (self.baseurl, pair)
            #print(url)
            j, r = await self._jsonget(url)
            #print(j)
            ask = Decimal(j['ask'])
            bid = Decimal(j['bid'])
            self.updateRates(p, ask, bid, j['timestamp'] / 1000.0)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        return self.WSClient(self)

    class WSClient(WebSocketClient):
        def __init__(self, service):
            super().__init__(service)
            self.url = "wss://api.hitbtc.com/api/2/ws"
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            #print("_on_connection_success()")
            for p in self.service.ratepairs():
                self.send({
                    "method": "subscribeOrderbook", # subscribeTicker
                    "params": {
                        "symbol": "%s%s" % (p[0], p[1])
                    },
                    "id": 123
                })
            pass
        def datestr2epoch(self, datestr):
            when = dateutil.parser.parse(datestr)
            return when.timestamp()
        def symbols2pair(self, symbol):
            return (symbol[:3], symbol[3:])
        def _on_message(self, msg):
            m = simplejson.loads(msg, use_decimal=True)
            #print(m)
            #print()
            if 'method' in m:
                if "ticker" == m['method']:
                    pair = self.symbols2pair(m['params']['symbol'])
                    self.service.updateRates(pair,
                                             m['params']['ask'],
                                             m['params']['bid'],
                                             self.datestr2epoch(m['params']['timestamp']),
                    )
                if "snapshotOrderbook" == m['method']:
                    pair = self.symbols2pair(m['params']['symbol'])
                    o = Orderbook()
                    for side in ('ask', 'bid'):
                        oside = {
                            'ask' : o.SIDE_ASK,
                            'bid' : o.SIDE_BID,
                        }[side]
                        #print(m['params'][side])
                        for e in m['params'][side]:
                            o.update(oside, Decimal(e['price']), Decimal(e['size']))
                    # FIXME setting our own timestamp, as there is no
                    # timestamp from the source.  Ask bl3p to set one?
                    o.setupdated(time.time())
                    self.service.updateOrderbook(pair, o)
                if "updateOrderbook" == m['method']:
                    pair = self.symbols2pair(m['params']['symbol'])
                    o = self.service.orderbooks[pair].copy()
                    for side in ('ask', 'bid'):
                        oside = {
                            'ask' : o.SIDE_ASK,
                            'bid' : o.SIDE_BID,
                        }[side]
                        for e in m['params'][side]:
                            price = Decimal(e['price'])
                            if '0.00' == e['size']:
                                o.remove(oside, price)
                            else:
                                volume = Decimal(e['size'])
                                o.update(oside, price, volume)
                    # FIXME setting our own timestamp, as there is no
                    # timestamp from the source.  Ask bl3p to set one?
                    o.setupdated(time.time())
                    self.service.updateOrderbook(pair, o)

class TestHitbtc(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Hitbtc(['BTC', 'USD'])
        configpath = expanduser('~/.config/valutakrambod/testsuite.ini')
        self.config = configparser.ConfigParser()
        self.config.read(configpath)
        self.s.confinit(self.config)
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
        pairs = self.s.ratepairs()
        for pair in pairs:
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)

    def checkWebsocket(self):
        """Test websocket subscription of updates.

        """
        def registerUpdate(service, pair, changed):
            if False:
                print(pair,
                      service.rates[pair]['ask'],
                      service.rates[pair]['bid'],
                      time.time() - service.rates[pair]['when'] ,
                      time.time() - service.rates[pair]['stored'] ,
                )
            self.updates += 1
            self.ioloop.stop()
        self.s.subscribe(registerUpdate)
        c = self.s.websocket()
        c.connect()
    def testWebsocket(self):
        self.updates = 0
        self.runCheck(self.checkWebsocket, timeout=10)
        self.assertTrue(0 < self.updates)

if __name__ == '__main__':
    t = TestHitbtc()
    unittest.main()
