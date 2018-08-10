# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import configparser
import simplejson
import time
import unittest
import tornado.ioloop

from decimal import Decimal
from os.path import expanduser
from tornado import ioloop

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.websocket import WebSocketClient

class Bitstamp(Service):
    """Query the Bitstamp API.  Documentation is available from
https://www.bitstamp.com/help/api#general-usage and
https://www.bitstamp.net/api/ .

https://www.bitstamp.net/websocket/, https://pusher.com/docs and
https://pusher.com/docs/pusher_protocol#websocket-connection document
the websocket API.

    """
    keymap = {
        'BTC' : 'XBT',
        }
    baseurl = "https://www.bitstamp.net/api/v2/"
    def servicename(self):
        return "Bitstamp"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ('BTC', 'EUR'),
            ('EUR', 'USD'),
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
            url = "%sticker/%s%s/" % (self.baseurl, f.lower(), t.lower())
            #print(url)
            # this call raise HTTP error with invalid currency.
            # should we catch it?
            j, r = await self._jsonget(url)
            #print(j)
            ask = Decimal(j['ask'])
            bid = Decimal(j['bid'])
            self.updateRates(p, ask, bid, int(j['timestamp']))
            res[p] = self.rates[p]
        return res
    class WSClient(WebSocketClient):
        _channelmap = {
            'order_book_bchbtc' : ('BCH', 'BTC'),
            'order_book_bcheur' : ('BCH', 'EUR'),
            'order_book_bchusd' : ('BCH', 'USD'),
            'order_book' :        ('BTC', 'USD'), # note, not order_book_btcusd
            'order_book_btceur' : ('BTC', 'EUR'),
            'order_book_ethbtc' : ('ETH', 'BTC'),
            'order_book_etheur' : ('ETH', 'EUR'),
            'order_book_ethusd' : ('ETH', 'USD'),
            'order_book_eurusd' : ('EUR', 'USD'),
            'order_book_ltcbtc' : ('LTC', 'BTC'),
            'order_book_ltceur' : ('LTC', 'EUR'),
            'order_book_ltcusd' : ('LTC', 'USD'),
            'order_book_xrpbtc' : ('XRP', 'BTC'),
            'order_book_xrpeur' : ('XRP', 'EUR'),
            'order_book_xrpusd' : ('XRP', 'USD'),
        }
        # Channels to subscribe to, should match ratepars() above
        _channels = [
            'order_book',
            'order_book_btceur',
            'order_book_eurusd',
        ]
        def __init__(self, service):
            super().__init__(service)
            self.url = "wss://ws.pusherapp.com/app/de504dc5763aeef9ff52?protocol=6&client=js&version=2.1.2&flash=false"
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            for c in self._channels:
                self.send({
                    "event": "pusher:subscribe",
                    "data": {
                        "channel": c,
                    }
                })
        def _on_message(self, msg):
            m = simplejson.loads(msg, use_decimal=True)
            #print(m)
            if 'data' == m['event']:
                o = Orderbook()
                d = simplejson.loads(m['data'], use_decimal=True)
                for side in ('asks', 'bids'):
                    oside = {
                        'asks' : o.SIDE_ASK,
                        'bids' : o.SIDE_BID,
                    }[side]
                    for e in d[side]:
                        o.update(oside, Decimal(e[0]), Decimal(e[1]))
                o.setupdated(int(d['timestamp']))
                self.service.updateOrderbook(self._channelmap[m['channel']], o)
    def websocket(self):
        return self.WSClient(self)

class TestBitstamp(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Bitstamp()
        configpath = expanduser('~/.config/valutakrambod/testsuite.ini')
        self.config = configparser.ConfigParser()
        self.config.read(configpath)
        self.s.confinit(self.config)
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
        pairs = self.s.ratepairs()
        for pair in pairs:
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
                  time.time() - service.rates[pair]['when'] ,
                  time.time() - service.rates[pair]['stored'] ,
            )
            self.ioloop.stop()
        self.s.subscribe(printUpdate)
        c = self.s.websocket()
        c.connect()
        self.ioloop.call_later(10, self.ioloop.stop)
        self.ioloop.start()

if __name__ == '__main__':
    t = TestBitstamp()
    unittest.main()
