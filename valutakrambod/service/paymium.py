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

from tornado.httpclient import HTTPError

from decimal import Decimal, ROUND_DOWN
from os.path import expanduser

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.services import Trading
from valutakrambod.socketio import SocketIOClient


class Paymium(Service):
    """Query the Paymium API.  Documentation is available from
https://github.com/Paymium/api-documentation/ and
https://github.com/Paymium/api-documentation/blob/master/WEBSOCKETS.md.

    """
    baseurl = "https://paymium.com/api/v1/"
    def servicename(self):
        return "Paymium"

    def ratepairs(self):
        return [
            ('BTC', 'EUR'),
            ]
    def _nonce(self):
        nonce = int(time.time()*100)
        #print("Using nonce %d" % nonce)
        return nonce
    async def _signedfetch(self, method, url, data):
        urlpath = urllib.parse.urlparse(url).path.encode('UTF-8')
        nonce = self._nonce()
        datastr = urllib.parse.urlencode(data)

        # "The API signature is the hexdigest of the HMAC-SHA256 hash
        # of the nonce concatenated with the full URL and body of the
        # HTTP request, encoded using your API secret key,"
        noncestr = str(nonce)
        message = (noncestr + url + datastr).encode('UTF-8')
        msgsignature = hmac.new(self.confget('apisecret').encode('UTF-8'),
                                message,
                                hashlib.sha256)
        sign = msgsignature.hexdigest()
        headers = {
            'API-Key' : self.confget('apikey'),
            'API-Nonce': noncestr,
            'API-Signature': sign,
            'Authorization': 'Bearer %s' % self.confget('apikey'),
        }
        if 'POST' == method:
                body, response = await self._post(url, body=datastr, headers=headers)
        else:
            body, response = await self._fetch(method, url, headers=headers)
        return body, response
    async def _query_private_fetch(self, method, action, args = {}):
        url = "%s%s" % (self.baseurl, action)
        body, response = await self._signedfetch(method, url, args)
        if body and '' != body:
            j = simplejson.loads(response.body.decode('UTF-8'), use_decimal=True)
            #print(j)
        else:
            j = None
        return j
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        #self._fetchTicker(pairs)
        await self._fetchOrderbooks(pairs)

    async def _fetchOrderbooks(self, pairs):
        now = time.time()
        for pair in pairs:
            f = pair[0]
            t = pair[1]
            url = "%sdata/%s/depth" % (self.baseurl, t.lower())
            #print(url)
            j, r = await self._jsonget(url)
            #print(j)
            o = Orderbook()
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for order in j[side]:
                    if t != order['currency']: # sanity check
                        raise Exception("unexpected currency returned by depth call")
                    #print("Updating %s", (side, order), now - order['timestamp'])
                    o.update(oside,
                             order['price'],
                             order['amount'],
                             order['timestamp'])
                #print(o)
            self.updateOrderbook(pair, o)

    async def _fetchTicker(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="X%sZ%s" % (f, t)
            #print(pair)
            url = "%sdata/%s/ticker" % (self.baseurl, t.lower())
            (j, r) = await self._jsonget(url)
            #print(r.code)
            if 200 != r.code:
                raise Error()
            #print(j)
            ask = j['ask']
            bid = j['bid']
            self.updateRates(p, ask, bid, j['at'])
            res[p] = self.rates[p]
        return res

    class SIOClient(SocketIOClient):
        def __init__(self, service):
            super().__init__(service)
            self.url = "wss://paymium.com/ws/socket.io/?transport=websocket"
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            self.subscribe('/public')
        def _on_event(self, channel, events):
            #print("_on_events('%s', '%s')" % (channel, events))
            t, m = events
            if 'stream' == t:
                self._on_stream_event(m)
            elif 'announcement' == t:
                # Ignore
                pass
            else:
                pass # unknown event type
        def _on_stream_event(self, data):
            for t in data.keys():
                if 'ticker' == t:
                    pair = ('BTC', data['ticker']['currency'])
                    self.service.updateRates(pair,
                                             data['ticker']['ask'],
                                             data['ticker']['bid'],
                                             data['ticker']['at'],
                    )
                # Hm, how can we know we start with the complete
                # ordebook when we start patching using bids and
                # asks?
                elif 'bids' == t:
                    pass
                elif 'asks' == t:
                    pass
                elif 'trades' == t:
                    # Ignore trades for now
                    pass
                else: # unknown stream data type, ignore for now
                    pass
    def websocket(self):
        return self.SIOClient(self)

    class PaymiumTrading(Trading):
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
        def roundtovalidprice(self, pair, side, price):
            """Round the given price to the nearest accepted value.  Paymium limit
            the number of digits for a given marked price and reject
            orders with more digits in the proposed price.

            """
            digits = {
                (('BTC','EUR'),Orderbook.SIDE_ASK): Decimal('.01'),
                (('BTC','EUR'),Orderbook.SIDE_BID): Decimal('.01'),
            }[(pair,side)]
            return price.quantize(digits, rounding=ROUND_DOWN)
        async def balance(self):
            """Fetch balance and restructure it to standardized return format,
using standard currency codes.  The return format is a hash with
currency code as the key, and a Decimal() value representing the
current balance.

This is example output from the API call:

{'error': [], 'result': {'KFEE': '0.00', 'BCH': '0.1', 'ZEUR': '1.234', 'XXLM': '1.32', 'XXBT': '1.24'}}

        """
            # Return cached balance if available and less then 10
            # seconds old to avoid triggering rate limit.
            #print('balance %s %s' % (self._lastbalance, time.time()))
            if self._lastbalance is not None and \
               self._lastbalance['timestamp'] + 10 > time.time():
                return self._lastbalance
            info = await self.service._query_private_fetch('GET', 'user', {})
            print("Balance:", info)
            res = { 'balance' : {}, 'available': {} }
            for key in info.keys():
                if 0 == key.find('balance_'):
                    c = key.split('_')[1].upper()
                    res['balance'][c] = info[key]
                    locked = info[key.replace('balance_', 'locked_')]
                    res['available'][c] = res['balance'][c] - locked
            self._lastbalance = res
            self._lastbalance['timestamp'] = time.time()
            return res
        async def placeorder(self, marketpair, side, price, volume, immediate=False):
            # Invalidate balance cache
            self._lastbalance = None

            if 'BTC' != marketpair[0]:
                raise Exception("invalid marked pair in placeorder")
            if price is None:
                ordertype = 'MarketOrder'
            else:
                ordertype = 'LimitOrder'
            type = {
                    Orderbook.SIDE_ASK : 'sell',
                    Orderbook.SIDE_BID : 'buy',
            }[side]
            args = {
                'currency': marketpair[1],
                'direction': type,
                'type': ordertype,
                'price': price,
                'amount': volume,
#                'oflags' : ,
#                'starttm' : ,
            }
            #print(args)
            try:
                res = await self.service._query_private_fetch('POST', 'user/orders', args)
                print(res)
            except HTTPError as e:
                print("error:", e.response.body)
                raise
            return (res['uuid'],)
        async def cancelorder(self, marketpair, orderref):
            # Invalidate balance cache
            self._lastbalance = None
            res = await self.service._query_private_fetch('DELETE', 'user/orders/%s/cancel' % orderref)
            # Nothing needs to be returned.  _query_private() will
            # throw if not successfull
            return
        async def cancelallorders(self, marketpair=None):
            raise NotImplementedError()
        async def orders(self, marketpair = None):
            """Return the currently open orders in standardized format."""

            orders = await self.service._query_private_fetch('GET', 'user/orders?active=true')
            """ Example output from the service
[{'currency_fee': Decimal('0.0'),
 'uuid': 'e028e5cd-3e96-4660-8ad5-094609df8aa3',
 'direction': 'sell',
 'currency_amount': None,
 'comment': None,
 'state': 'active',
 'updated_at': '2018-05-05T15:48:10Z',
 'traded_currency': Decimal('0.0'),
 'traded_btc': Decimal('0.0'),
 'amount': Decimal('0.1'),
 'currency': 'EUR',
 'created_at': '2018-05-05T15:48:32Z',
 'type': 'LimitOrder',
 'price': Decimal('8300.0'),
 'btc_fee': Decimal('0.0'),
 'account_operations': [
    {'is_trading_account': False,
     'uuid': 'ee34824e-2520-4785-8e75-066755979556',
     'amount': Decimal('-0.1'),
     'currency': 'BTC',
     'created_at': '2018-05-05T15:48:32Z',
     'name': 'lock',
     'created_at_int': 1525535312
    },
    {'is_trading_account': True,
 'uuid': '74892eea-f278-4423-80f4-31591c481d6e',
 'amount': Decimal('0.1'),
 'currency': 'BTC',
 'created_at': '2018-05-05T15:48:32Z',
 'name': 'lock',
 'created_at_int': 1525535312}
 ]
}]
"""
            #print(orders)
            res = {}
            for order in orders:
                id = order['uuid']
                type = { 'buy': 'bid', 'sell':'ask'}[order['direction']]
                pair = ('BTC', order['currency'])
                volume = order['amount']
                price = order['price']
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
            """From https://www.paymium.com/help/fees, the max fee is 0.26%.

            """
            fee = price * volume * Decimal(0.0026)
            #print("Paymium fee %s * %s * %s = %s" % (
            #    price, volume, Decimal('0.0026'), fee,
            #))
            return fee
    def trading(self):
        if self.confget('apikey', fallback=None) is None:
            if False:
                print("no apikey for %s in ini file, not trading" %
                      self.servicename())
            return None
        if self.activetrader is None:
            self.activetrader = self.PaymiumTrading(self)
        return self.activetrader


class TestPaymium(unittest.TestCase):
    """
Run simple self test of the Paymium service class.
"""
    def setUp(self):
        self.s = Paymium()
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

    async def checkFetchTicker(self):
        res = await self.s._fetchTicker()
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
        self.ioloop.stop()
    def testFetchTicker(self):
        self.runCheck(self.checkFetchTicker)

    async def checkFetchOrderbooks(self):
        pairs = self.s.ratepairs()
        await self.s._fetchOrderbooks(pairs)
        for pair in pairs:
            self.assertTrue(pair in self.s.rates)
            self.assertTrue(pair in self.s.orderbooks)
            ask = self.s.rates[pair]['ask']
            bid = self.s.rates[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            self.assertTrue(spread > 0 and spread < 5)
        self.ioloop.stop()
    def testFetchOrderbooks(self):
        self.runCheck(self.checkFetchOrderbooks)

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
        o = await t.orders()
        print("Orders:", o)

        rates = await self.s.currentRates()
        ask = rates[pair]['ask']
        bid = rates[pair]['bid']

        # place test order 50% above current ask price
        askprice = t.roundtovalidprice(pair, Orderbook.SIDE_ASK, ask * Decimal(1.5))

        # place test order 50% below current bid price
        bidprice = t.roundtovalidprice(pair, Orderbook.SIDE_BID, bid * Decimal(0.5))

        #print("Ask %s -> %s" % (ask, askprice))
        #print("Bid %s -> %s" % (bid, bidprice))

        balance = 0
        bidamount = Decimal('0.002')
        b = await t.balance()
        #print("Balance:", b)
        if pair[1] in b['available']:
            balance = b['available'][pair[1]]
        if balance > bidamount:
            print("placing buy order %s %s at %s %s" % (bidamount, pair[0], bidprice, pair[1]))
            txs = await t.placeorder(pair, Orderbook.SIDE_BID,
                                     bidprice, bidamount, immediate=False)
            print("placed orders: %s" % txs)
            for tx in txs:
                print("cancelling order %s" % tx)
                j = await t.cancelorder(pair, tx)
                print("done cancelling")
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (bidamount, pair[1], balance))

        balance = 0
        askamount = Decimal('0.002')
        b = await t.balance()
        if pair[0] in b['available']:
            balance = b['available'][pair[0]]
        if balance > askamount:
            print("placing sell order %s %s at %s %s" % (askamount, pair[0], askprice, pair[1]))
            txs = await t.placeorder(pair, Orderbook.SIDE_ASK,
                                     askprice, askamount, immediate=False)
            print("placed orders: %s" % txs)
            for tx in txs:
                print("cancelling order %s" % tx)
                j = await t.cancelorder(pair, tx)
                print("done cancelling")
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (askamount, pair[0], balance))

        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

    async def checkBalanceCaching(self):
        t = self.s.trading()
        if not t:
            self.ioloop.stop()
            return
        b1 = await t.balance()
        b2 = await t.balance()
        self.assertTrue(b1['timestamp'] == b2['timestamp'])
        self.ioloop.stop()
    def testBalanceCaching(self):
        self.runCheck(self.checkBalanceCaching)


if __name__ == '__main__':
    t = TestPaymium()
    unittest.main()
