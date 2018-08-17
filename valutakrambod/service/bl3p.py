# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import base64
import configparser
import decimal
import hashlib
import hmac
import simplejson
import time
import tornado.ioloop
import unittest
import urllib

from os.path import expanduser

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.services import Trading
from valutakrambod.websocket import WebSocketClient

class Bl3p(Service):
    """
Query the Bl3p API.  Documentation is available from
https://bl3p.eu/api .
"""
    baseurl = "https://api.bl3p.eu/1/"
    async def _signedpost(self, url, data):
        path = url.replace(self.baseurl, '')
        datastr = urllib.parse.urlencode(data)

        # API-Sign = Message signature using HMAC-SHA512 of (URI path +
        # null terminator + POST data) and base64 decoded secret API key
        message = "%s%c%s" % (path, 0x00, datastr)
        print(message)
        privkey_bin = base64.b64decode(self.confget('apisecret'))
        msgsignature = hmac.new(privkey_bin, message.encode(), hashlib.sha512).digest()
        sign = base64.b64encode(msgsignature)
        headers = {
            'Rest-Key' : self.confget('apikey'),
            'Rest-Sign': sign.decode(),
        }

        body, response = await self._post(url, datastr, headers)
        return body, response
    async def _query_private(self, method, args):
        url = "%s%s" % (self.baseurl, method)
        body, response = await self._signedpost(url, args)
        j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
        print(j)
        if 'success' != j['result']:
            raise Exception('unable to query %s: %s' % (method, j['error']))
        return j['data']

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

    class Bl3pTrading(Trading):
        def __init__(self, service):
            self.service = service
        def setkeys(self, apikey, apisecret):
            """Add the user specific information required by the trading API in
clear text to the current configuration.  These settings can also be
loaded from the stored configuration.

            """
            self.service.confset('apikey', apikey)
            self.service.confset('apisecret', apisecret)
        async def balance(self):
            """Fetch balance and restructure it to standardized return format,
using standard currency codes.  The return format is a hash with
currency code as the key, and a Decimal() value representing the
current balance.

This is example output from the API call:

N/A

"""
            assets = await self.service._query_private('GENMKT/money/info', {})
            print(assets)
            res = {}
            for asset in assets['wallets'].keys():
                res[asset] = decimal.Decimal(assets['wallets'][asset]['balance']['value'])
            return res
    def trading(self):
        if self.activetrader is None:
            self.activetrader = self.Bl3pTrading(self)
        return self.activetrader

class TestBl3p(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Bl3p()
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
        pair = ('BTC', 'EUR')
        self.assertTrue(pair in res)
        ask = res[pair]['ask']
        bid = res[pair]['bid']
        self.assertTrue(ask >= bid)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)
    async def checkWebsocket(self):
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
    def testWebsocket(self):
        self.runCheck(self.checkWebsocket)
    async def checkTradingConnection(self):
        # Unable to test without API access credentials in the config
        if self.s.confget('apikey', fallback=None) is None:
            print("no apikey for %s in ini file, not testing trading" %
                  self.s.servicename())
            self.ioloop.stop()
            return
        t = self.s.trading()
        b = await t.balance()
        print(b)
        return # FIXME The rest is not implemented
        print(await t.orders())
        print("trying to place order")
        if 'EUR' in b and b['EUR'] > 0.1:
            print("placing order")
            pairstr = self.s._makepair('BTC', 'EUR')
            txs = await t.placeorder(pairstr, Orderbook.SIDE_BID,
                                   0.1, 0.1, immediate=False)
            print("placed orders: %s" % txs)
            for tx in txs:
                print("cancelling order %s" % tx)
                j = await t.cancelorder(tx)
                print("done cancelling: %s" % str(j))
                self.assertTrue('count' in j and j['count'] == 1)
        else:
            print("unable to place 1 EUR order, lacking funds")
        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)
if __name__ == '__main__':
    t = TestBl3p()
    unittest.main()
