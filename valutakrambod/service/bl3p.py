# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import base64
import configparser
import hashlib
import hmac
import simplejson
import time
import tornado.ioloop
import unittest
import urllib

from decimal import Decimal
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
        #print(message)
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
        #print(j)
        if 'success' != j['result']:
            raise Exception('unable to query %s: %s' % (method, j['data']['message']))
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
            ask = Decimal(j['ask'])
            bid = Decimal(j['bid'])
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
                    o.update(oside, Decimal(e['price_int']) / 100000,
                             Decimal(e['amount_int']) / 100000000 )
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
            self._lastbalance = None
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
            # Return cached balance if available and less then 10
            # seconds old to avoid triggering rate limit.
            if self._lastbalance is not None and \
               self._lastbalance['_timestamp'] + 10 > time.time():
                return self._lastbalance
            assets = await self.service._query_private('GENMKT/money/info', {})
            #print(assets)
            res = {}
            for asset in assets['wallets'].keys():
                res[asset] = Decimal(assets['wallets'][asset]['balance']['value'])
            self._lastbalance = res
            self._lastbalance['_timestamp'] = time.time()
            return res
        async def placeorder(self, marketpair, side, price, volume, immediate=False):
            # Invalidate balance cache
            self._lastbalance = None
            type = {
                    Orderbook.SIDE_ASK : 'ask',
                    Orderbook.SIDE_BID : 'bid',
            }[side]
            data = {
                'type': type,
#                'amount_funds_int': ,# Limit order to this amount of EUR
                'fee_currency': 'EUR',
            }
            if price is not None:
                # Price in EUR (*1e5)
                data['price_int'] = int(price * 100000)
            else:
                raise ValueError("placeorder() without price currently not supported")
            # Ask for this amount of BTC / 1Eu (ie Satochi)
            data['amount_int'] = int(volume * 100000000)

            method = '%s/money/order/add' % marketpair
            order = await self.service._query_private(method, data)
            order_id = order['order_id']
            return order_id
        async def cancelorder(self, marketpair, orderref):
            # Invalidate balance cache
            self._lastbalance = None
            data = {
                'order_id': orderref,
            }
            order = await self.service._query_private('%s/money/order/cancel'
                                                       % marketpair, data)
            # Nothing to return.  _query_private() will throw if not successfull
            return
        async def cancelallorders(self, marketpair):
            raise NotImplementedError()
        async def orders(self, marketpair = None):
            """Return the currently open orders in standardized format.

FIXME The format is yet to be standardized.

"""
            res = await self.service._query_private('%s/money/orders' % marketpair, {})
            print(res)
        def estimatefee(self, side, price, volume):
            """From https://bl3p.eu/fees:
  Rade fee
  Flat fee of 0,25% + € 0,01 per executed order.

Using our set price to calculate amount for fixed fee, as our price
have to be closed to the used price if our order is executed.

            """
            return price * volume * Decimal(0.0025) + Decimal(0.01)
    def trading(self):
        if self.confget('apikey', fallback=None) is None:
            return None
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

        pair = ('BTC', 'EUR')
        pairstr = "%s%s" % pair
        o = await t.orders(pairstr)
        print(o)

        rates = await self.s.currentRates()
        ask = rates[pair]['ask']
        bid = rates[pair]['bid']
        askprice = ask * Decimal(1.5) # place test order 50% above current ask price
        bidprice = bid * Decimal(0.5) # place test order 50% below current bid price
        #print("Ask %s -> %s" % (ask, askprice))
        #print("Bid %s -> %s" % (bid, bidprice))

        balance = 0
        bidamount = Decimal('0.01')
        b = await t.balance()
        if pair[1] in b:
            balance = b[pair[1]]
        if balance > bidamount:
            print("placing buy order %s %s at %s %s" % (bidamount, pair[0], bidprice, pair[1]))
            tx = await t.placeorder(pairstr, Orderbook.SIDE_BID,
                                    bidprice, bidamount, immediate=False)
            print("placed order with id %s" % tx)
            print("cancelling order %s" % tx)
            await t.cancelorder(pairstr, tx)
            print("done cancelling: %s")
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (bidamount, pair[1], balance))

        balance = 0
        askamount = Decimal('0.01')
        b = await t.balance()
        if pair[0] in b:
            balance = b[pair[0]]
        if balance > askamount:
            print("placing sell order %s %s at %s %s" % (askamount, pair[1], askprice, pair[0]))
            tx = await t.placeorder(pairstr, Orderbook.SIDE_ASK,
                                    askprice, askamount, immediate=False)
            print("placed order with id %s" % tx)
            print("cancelling order %s" % tx)
            await t.cancelorder(pairstr, tx)
            print("done cancelling: %s" % tx)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (askamount, pair[0], balance))

        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

    async def checkBalanceCaching(self):
        t = self.s.trading()
        b1 = await t.balance()
        b2 = await t.balance()
        self.assertTrue(b1['_timestamp'] == b2['_timestamp'])
        self.ioloop.stop()
    def testBalanceCaching(self):
        self.runCheck(self.checkBalanceCaching)

if __name__ == '__main__':
    t = TestBl3p()
    unittest.main()
