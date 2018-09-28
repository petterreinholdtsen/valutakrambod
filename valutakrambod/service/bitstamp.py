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

from decimal import Decimal, ROUND_DOWN
from os.path import expanduser
from tornado import ioloop

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.services import Trading
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
    baseurl = "https://www.bitstamp.net/api/"
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
    def _makepair(self, f, t):
        return "%s%s" % (self._currencyMap(f), self._currencyMap(t))
    def _nonce(self):
        # Use same nonce as Finance::BitStamp::API perl module
        nonce = int(time.time()*1000000)
        return nonce
    async def _signedpost(self, url, data):
        customerid = self.confget('customerid')
        if data is None:
            data = {}
        data['key'] = self.confget('apikey')
        data['nonce'] = str(self._nonce())
        message = data['nonce'] + customerid + data['key']
        sign = hmac.new(self.confget('apisecret').encode('UTF-8'),
                                msg=message.encode('UTF-8'),
                                digestmod=hashlib.sha256).hexdigest().upper()
        data['signature'] =  sign
        datastr = urllib.parse.urlencode(data)
        #print(datastr)
        body, response = await self._post(url, datastr)
        return body, response
    async def _query_private(self, method, args):
        url = "%s%s" % (self.baseurl, method)
        body, response = await self._signedpost(url, args)
        j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
        return j
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            url = "%sv2/ticker/%s%s/" % (self.baseurl, f.lower(), t.lower())
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
                        # Note, some times volume is zero.  No idea what that mean.
                        o.update(oside, Decimal(e[0]), Decimal(e[1]))
                o.setupdated(int(d['timestamp']))
                self.service.updateOrderbook(self._channelmap[m['channel']], o)
    def websocket(self):
        return self.WSClient(self)
    class BitstampTrading(Trading):
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
            # Return cached balance if available and less then 10
            # seconds old to avoid triggering rate limit.
            print('balance %s %s' % (self._lastbalance, time.time()))
            if self._lastbalance is not None and \
               self._lastbalance['_timestamp'] + 10 > time.time():
                return self._lastbalance

            assets = await self.service._query_private('v2/balance/', {})
            #print(assets)
            res = {}
            for entry in sorted(assets.keys()):
                instrument, type = entry.split('_')
                value = Decimal(assets[entry])
                #print(instrument, type, value)
                # FIXME should we use balance, reserved or available?
                if 'balance' == type and 0 != value:
                    res[instrument.upper()] = value
            self._lastbalance = res
            self._lastbalance['_timestamp'] = time.time()
            return res
        async def placeorder(self, marketpair, side, price, volume, immediate=False):
            # Invalidate balance cache
            self._lastbalance = None

            pairstr = ("%s%s" % (marketpair[0], marketpair[1])).lower()
            if price is None:
                ordertype = 'market/'
            else:
                ordertype = ''
            type = {
                    Orderbook.SIDE_ASK : 'sell',
                    Orderbook.SIDE_BID : 'buy',
            }[side]
            urlpath = "v2/%s/%s%s/" % (type, ordertype, pairstr)
            #print(urlpath)

            data = {
                'amount': volume,
            }
            if price:
                data['price'] = price
            # Limit order can have these arguments as well:
            #data['limit_price'] = ?
            #data['daily_order'] = ?
            if immediate:
                data['ioc_order'] = True
            #print(data)
            res = await self.service._query_private(urlpath, data)
            #print(res)
            if 'error' in res and 'error' == res['status']:
                raise Exception('placing %s order failed' % type)
            return int(res['id'])
        async def cancelorder(self, marketpair, orderref):
            data = {
                'id': orderref,
            }
            res = await self.service._query_private('v2/cancel_order/', data)
            # Nothing to return.  _query_private() will throw if not successfull
            return res
        async def cancelallorders(self, marketpair=None):
            res = await self.service._query_private('cancel_all_orders/', {})
            # Nothing needs to be returned.  _query_private() will
            # throw if not successfull
            return res
        async def orders(self, marketpair = None):
            """Return the currently open orders in standardized format."""

            pairstr = 'all/'
            if marketpair:
                pairstr = ("%s%s" % (marketpair[0], marketpair[1])).lower()
            orders = await self.service._query_private('v2/open_orders/%s/' % pairstr, {})
            #print(orders)
            """ Example output from the service
[
 {'type': '0',
  'id': '2207850769',
  'currency_pair': 'BTC/EUR',
  'datetime': '2018-09-28 09:19:56',
  'amount': '0.00200000',
  'price': '2859.99'}
]
"""
            res = {}
            for order in orders:
                id = order['id']
                type = { '0': 'bid', '1':'ask'}[order['type']]
                pair = order['currency_pair'].split('/')
                volume = Decimal(order['amount'])
                price = Decimal(order['price'])
                if pair not in res:
                    res[pair] = {}
                if type not in res:
                    res[pair][type] = []
                res[pair][type].append({
                    "price": price,
                    "volume": volume,
                    "id": id,
                })
            for pair in res.keys():
                if 'ask' in res[pair]:
                    res[pair]['ask'] = sorted(res[pair]['ask'], key=lambda k: k['price'], reverse=True)
                if 'bid' in res[pair]:
                    res[pair]['bid'] = sorted(res[pair]['bid'], key=lambda k: k['price'])
            #print(res)
            return res
        def estimatefee(self, side, price, volume):
            """From https://www.bitstamp.net/fee_schedule/:

            ALL TRADING PAIRS (CUMULATIVE)
            Fee %	30 days USD volume
            0.25%	< $20,000
            [...]

Using our set price to calculate amount for fixed fee, as our price
have to be closed to the used price if our order is executed.

            """
            return price * volume * Decimal(0.0025)
    def trading(self):
        if self.activetrader is None:
            self.activetrader = self.BitstampTrading(self)
        return self.activetrader


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
    async def checkTradingConnection(self):
        # Unable to test without API access credentials in the config
        if self.s.confget('apikey', fallback=None) is None:
            print("no apikey for %s in ini file, not testing trading" %
                  self.s.servicename())
            self.ioloop.stop()
            return
        t = self.s.trading()

        pair = ('BTC', 'EUR')
        pairstr = self.s._makepair(pair[0], pair[1])
        o = await t.orders()
        print(o)

        c = await t.cancelallorders()
        print(c)

        rates = await self.s.currentRates()
        ask = rates[pair]['ask']
        bid = rates[pair]['bid']
        askprice = ask * Decimal(1.5) # place test order 50% above current ask price
        askprice = askprice.quantize(Decimal('.01'), rounding=ROUND_DOWN)
        bidprice = bid * Decimal(0.5) # place test order 50% below current bid price
        bidprice = bidprice.quantize(Decimal('.01'), rounding=ROUND_DOWN)
        #print("Ask %s -> %s" % (ask, askprice))
        #print("Bid %s -> %s" % (bid, bidprice))

        balance = 0
        bidamount = Decimal('0.01')
        b = await t.balance()
        if pair[1] in b:
            balance = b[pair[1]]
        if balance > bidamount:
            print("placing buy order %s %s at %s %s" % (bidamount, pair[0], bidprice, pair[1]))
            tx = await t.placeorder(pair, Orderbook.SIDE_BID,
                                     bidprice, bidamount, immediate=False)
            print("placed orders: %s" % tx)
            print("cancelling order %s" % tx)
            j = await t.cancelorder(pairstr, tx)
            print("done cancelling: %s" % str(j))
            self.assertTrue('id' in j and j['id'] == tx)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (bidamount, pair[1], balance))

        balance = 0
        askamount = Decimal('0.001')
        b = await t.balance()
        if pair[0] in b:
            balance = b[pair[0]]
        if balance > askamount:
            print("placing sell order %s %s at %s %s" % (askamount, pair[0], askprice, pair[1]))
            tx = await t.placeorder(pair, Orderbook.SIDE_ASK,
                                     askprice, askamount, immediate=False)
            print("placed orders: %s" % tx)
            print("cancelling order %s" % tx)
            j = await t.cancelorder(pairstr, tx)
            print("done cancelling: %s" % str(j))
            self.assertTrue('id' in j and j['id'] == tx)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (askamount, pair[0], balance))

        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

if __name__ == '__main__':
    t = TestBitstamp()
    unittest.main()
