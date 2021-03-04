# -*- coding: utf-8 -*-
# Copyright (c) 2021 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import base64
import hashlib
import hmac
import re
import time
import unittest
import urllib

import configparser
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from os.path import expanduser
import simplejson
import tornado.ioloop

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.services import Trading

class Nbx(Service):
    """Query the Norwegian Block Exchange AS API.  Based on documentation
found in https://nbx.com/developers .
    """
    baseurl = "https://api.nbx.com"

    def servicename(self):
        return "NBX"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ]

    def _makepair(self, f, t) -> str:
        return "%s-%s" % (f, t)


    def _calculate_signature(self,
            timestamp: str,
            method: str,
            path: str,
            body: str,
            secret: str
    ):
        body_bytes = (timestamp + method + path + body).encode('UTF-8')
        secret_bytes = base64.b64decode(secret)
        signature_bytes = \
            hmac.new(secret_bytes, body_bytes, hashlib.sha256)\
                .digest()
        return base64.b64encode(signature_bytes).decode('UTF-8')


    async def _refresh_token(self) -> str:
        token_lifetime_in_minutes = self.confget('token_lifetime', 10)
        now = time.time()
        if not getattr(self, 'token', None):
            self.token = None
            self.token_timestamp = 0
        timeout = self.token_timestamp + token_lifetime_in_minutes * 60
        if self.token and now < timeout:
            return self.token
        account_id = self.confget('account_id')
        apikey = self.confget('apikey')
        passphrase = self.confget('passphrase')
        apisecret = self.confget('apisecret')
        timestamp = str(int(time.time() * 1000))
        path = f'/accounts/{account_id}/api_keys/{apikey}/tokens'
        body = '{"expiresIn": %d}' % token_lifetime_in_minutes
        method = 'POST'
        signature = self._calculate_signature(timestamp, method,
                                             path, body, apisecret)

        headers = {
            'Authorization':   f'NBX-HMAC-SHA256 {passphrase}:{signature}',
            'X-NBX-TIMESTAMP': timestamp
        }
        url = "%s%s" % (self.baseurl, path)
        body, response = await self._post(url, body=body, headers=headers)
        j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
        self.token = j['token']
        self.token_timestamp = now
        return self.token


    async def _query_private(self, path, args = None, method = None):
        token = await self._refresh_token()
        headers = {'Authorization': f'Bearer {self.token}'}
        account_id = self.confget('account_id')
        path = path.replace('{account_id}', account_id)
        if -1 == path.find('https://'):
            url = "%s%s" % (self.baseurl, path)
        else:
            url = path
        if 'POST' == method:
            body, response = await self._post(url, body=simplejson.dumps(args),
                                              headers=headers)
            j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
        elif 'DELETE' == method:
            body, response = await self._fetch(method, url, headers=headers)
            if body and '' != body:
                j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
            else:
                j = None, response
            return j, response
        else: # GET
            j, response = await self._jsonget(url, headers=headers)
        return j, response


    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.wantedpairs
        await self.fetchOrderbooks(pairs)

    async def fetchOrderbooks(self, pairs):
        for pair in pairs:
            o = Orderbook()
            url = "%s/markets/%s-%s/orders" % (self.baseurl, pair[0], pair[1])
            #print(url)
            j, r = await self._jsonget(url)
            #print(j)
            for order in j:
                oside = {
                    'BUY': o.SIDE_BID,
                    'SELL' : o.SIDE_ASK,
                }[order['side']]
                o.update(oside, Decimal(order['price']), Decimal(order['quantity']))
                #print(pair, order['side'], Decimal(order['price']), Decimal(order['quantity']))
            self.updateOrderbook(pair, o)

    def websocket(self):
        """NBX do not seem to provide websocket API 2021-02-27."""
        return None

    class NbxTrading(Trading):
        def __init__(self, service):
            self.service = service
            self._lastbalance = None


        def roundtovalidprice(self, pair, side, price):
            # The API require prices to be a multiple of 0.01, but
            # this is not mentioned in the documentation 2021-03-02.
            digits = {
                (('BTC','NOK'),Orderbook.SIDE_ASK): Decimal('.01'),
                (('BTC','EUR'),Orderbook.SIDE_ASK): Decimal('.01'),
                (('BTC','NOK'),Orderbook.SIDE_BID): Decimal('.01'),
                (('BTC','EUR'),Orderbook.SIDE_BID): Decimal('.01'),
            }[(pair,side)]
            return price.quantize(digits, rounding=ROUND_DOWN)


        async def balance(self):
            # Return cached balance if available and less then 10
            # seconds old to avoid triggering rate limit.
            #print('balance %s %s' % (self._lastbalance, time.time()))
            if self._lastbalance is not None and \
               self._lastbalance['timestamp'] + 10 > time.time():
                return self._lastbalance

            assets, response = await self.service._query_private(
                '/accounts/{account_id}/assets')
            #print(assets)
            res = { 'balance' : {}, 'available': {} }
            for entry in assets:
                instrument = entry['id']
                balance = Decimal(entry['balance']['total'])
                available = Decimal(entry['balance']['available'])
                res['balance'][instrument] = balance
                res['available'][instrument] = available
            self._lastbalance = res
            self._lastbalance['timestamp'] = time.time()
            #print(res)
            return res


        async def placeorder(self, marketpair, side, price, volume, immediate=False):
            method = 'POST'
            path = '/accounts/{account_id}/orders'
            market = self.service._makepair(marketpair[0], marketpair[1])
            side = {
                Orderbook.SIDE_BID: 'BUY',
                Orderbook.SIDE_ASK: 'SELL',
            }[side]
            if immediate:
                execution = {
                    "type": "MARKET",
                    # ...
                }
                raise NotImplementedError() # FIXME
            else:
                execution = {
                    "type": "LIMIT",
                    "price": str(price),
                    "timeInForce": { "type": "GOOD_TIL_CANCELED" },
                }
            body = {
                "market": market,
                "quantity": str(volume),
                "side": side,
                "execution": execution,
            }
            #print(method, path, body)
            j, response = \
                await self.service._query_private(path, body, method='POST')
            location = response.headers['Location']
            #print("Location:", location)
            m = re.match(r'^.*/accounts/.+/orders/(.+)$', location)
            id = m.group(1)
            return id


        async def cancelorder(self, marketpair, order_id):
            market_id = self.service._makepair(marketpair[0], marketpair[1])
            path = f'/markets/{market_id}/orders/{order_id}'
            j, response = \
                await self.service._query_private(path, method='DELETE')
            return j


        async def cancelallorders(self, marketpair=None):
            raise NotImplementedError() # FIXME implement


        async def orders(self, marketpair = None):
            path = '/accounts/{account_id}/orders'
            res = {}
            while path:
                #print("Orders %s" % path)
                orders, response = await self.service._query_private(path)
                #print(response.headers)
                # Handle pagination, fetch all orders
                # FIXME figure out if we can filter out the orders we want
                if 'X-Next-Page-Url' in response.headers:
                    path = response.headers['X-Next-Page-Url']
                else:
                    path = None

                # FIXME filter out the marketpair entries we want
                for order in orders:
# Example:
#{
#    'id': '91a867cc-7b51-11eb-a04b-7613bb333b76',
#    'quantity': '0.46493463',
#    'side': 'SELL',
#    'execution': {
#        'price': '430983.37',
#        'type': 'LIMIT',
#        'timeInForce': {
#            'type': 'GOOD_TIL_CANCELED'
#        }
#    },
#    'fills': [],
#    'events': {
#        'createdAt': '2021-03-02T12:19:43.125000+00:00',
#        'openedAt': '2021-03-02T12:19:43.422000+00:00',
#        'closedAt': None,
#        'rejectedAt': None
#    },
#    'market': 'BTC-NOK'
#}

                    if order['events']['closedAt']:
                        continue # Only return open orders
                    volume = order['quantity']
                    price = order['execution']['price']
                    pair = tuple(order['market'].split('-', 1))
                    type = {
                        'SELL' : Orderbook.SIDE_ASK,
                        'BUY' : Orderbook.SIDE_BID,
                    }[order['side']]
                    id = order['id']
                    if pair not in res:
                        res[pair] = {}
                    if type not in res[pair]:
                        res[pair][type] = []
                    res[pair][type].append({
                        "price": price,
                        "volume": volume,
                        "id": id,
                    })
            for pair in res.keys():
                if 'ask' in res[pair]:
                    res[pair]['ask'] = sorted(res[pair]['ask'], key=lambda k: k['price'])
                if 'bid' in res[pair]:
                    res[pair]['bid'] = sorted(res[pair]['bid'], key=lambda k: k['price'], reverse=True)
            #print(res)
            return res


        def estimatefee(self, side, price, volume):
            """From
            https://nbxsupport.zendesk.com/hc/en-us/articles/360025617132-What-are-the-fees-on-NBX-:
            Fees are paid on a per-executed-trade basis. Any fees will
            be applied to the order at the time an order is
            placed. For partially filled orders, only the executed
            part of the order is subject to trading fees.

            * Maker: 0.5% (50 basis points)
            * Taker: 0.5% (50 basis points)

            """
            fee = price * volume * Decimal(0.005)
            return fee.quantize(Decimal('.01'), rounding=ROUND_UP)


    def trading(self):
        if self.confget('apikey', fallback=None) is None:
            return None
        if self.activetrader is None:
            self.activetrader = self.NbxTrading(self)
        return self.activetrader


class TestNbx(unittest.TestCase):
    """Simple self test.

    """
    def setUp(self):
        self.s = Nbx(['BTC', 'NOK', 'EUR'])
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
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            #print("Spread for %s:" % str(pair), spread)
            self.assertTrue(0 < spread and spread < 100)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)
    async def checkCompareOrderbookTicker(self):
        # Try to detect when the two ways to fetch the ticker disagree
        asks = {}
        bids = {}
        laststore = newstore = 0
        res = await self.s.fetchOrderbooks(self.s.wantedpairs)
        for pair in self.s.wantedpairs:
            asks[pair] = self.s.rates[pair]['ask']
            bids[pair] = self.s.rates[pair]['bid']
            if laststore < self.s.rates[pair]['stored']:
                laststore = self.s.rates[pair]['stored']
        res = await self.s.fetchRates(self.s.wantedpairs)
        for pair in self.s.wantedpairs:
            if asks[pair] != self.s.rates[pair]['ask']:
                print("ask order book (%.1f and ticker (%.1f) differ for %s" % (
                    asks[pair],
                    self.s.rates[pair]['ask'],
                    pair
                ))
                self.assertTrue(False)
            if bids[pair] != self.s.rates[pair]['bid']:
                print("bid order book (%.1f and ticker (%.1f) differ for %s" % (
                    bids[pair],
                    self.s.rates[pair]['bid'],
                    pair
                ))
                self.assertTrue(False)
            if newstore < self.s.rates[pair]['stored']:
                newstore = self.s.rates[pair]['stored']
            #print(laststore, newstore)
            self.assertTrue(laststore != newstore)
        self.ioloop.stop()
    def testCompareOrderbookTicker(self):
        self.runCheck(self.checkCompareOrderbookTicker)

    async def checkTradingConnection(self):
        # Unable to test without API access credentials in the config
        if self.s.confget('apikey', fallback=None) is None:
            print("no apikey for %s in ini file, not testing trading" %
                  self.s.servicename())
            self.ioloop.stop()
            return
        t = self.s.trading()

        b = await t.balance()

        pair = ('BTC', 'NOK')
        pairstr = self.s._makepair(pair[0], pair[1])
        o = await t.orders()
        #print("Orders:", o)

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
        bidamount = Decimal('0.001')
        b = await t.balance()
        #print('Balance:', b)
        if pair[1] in b['available']:
            balance = b['available'][pair[1]]
        if balance > bidamount * bidprice:
            print("placing buy order %s %s at %s %s" % (bidamount, pair[0], bidprice, pair[1]))
            tx = await t.placeorder(pair, Orderbook.SIDE_BID,
                                     bidprice, bidamount, immediate=False)
            print("cancelling order %s" % tx)
            j = await t.cancelorder(pair, tx)
        else:
            print("unable to place %s @ %s %s order, balance only had %s"
                  % (bidamount, bidprice, pair[1], balance))

        balance = 0
        askamount = Decimal('0.001')
        b = await t.balance()
        if pair[0] in b['available']:
            balance = b['available'][pair[0]]
        if balance > askamount:
            print("placing sell order %s %s at %s %s" % (askamount, pair[0], askprice, pair[1]))
            tx = await t.placeorder(pair, Orderbook.SIDE_ASK,
                                     askprice, askamount, immediate=False)
            print("cancelling order %s" % tx)
            j = await t.cancelorder(pair, tx)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (askamount, pair[0], balance))

        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

    def testRoundingPrices(self):
        t = self.s.trading()
        if not t:
            print("trading for %s not enabled, no way to test rounding rules" %
                  self.s.servicename())
            return
        pair = ('BTC', 'NOK')
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.1')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.11')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.111')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.117')))

        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.1')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.11')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.111')))
        self.assertEqual(Decimal('0.11'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.117')))

if __name__ == '__main__':
    t = TestNbx()
    unittest.main()
