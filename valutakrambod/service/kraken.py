# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import base64
import configparser
import hashlib
import hmac
import simplejson
import time
import unittest
import urllib
import urllib.parse
import tornado.ioloop

from decimal import Decimal, ROUND_DOWN
from os.path import expanduser

from valutakrambod.services import Orderbook
from valutakrambod.services import Service
from valutakrambod.services import Trading
from valutakrambod.websocket import WebSocketClient

class Kraken(Service):
    """
Query the Kraken API.  Documentation is available from
https://www.kraken.com/help/api#general-usage and
https://www.kraken.com/features/websocket-api .
"""
    keymap = {
        'BTC' : 'XXBT',
        'XLM' : 'XXLM',
        'EUR' : 'ZEUR',
        'USD' : 'ZUSD',
# Pass these through unchanged
#        'KFEE'
#        'BCH'
        }
    baseurl = "https://api.kraken.com/0/public/"
    privatebaseurl = "https://api.kraken.com/0/private/"
    def servicename(self):
        return "Kraken"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ('BTC', 'EUR'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    def _revCurrencyMap(self, asset):
        for stdasset in self.keymap.keys():
            if asset == self.keymap[stdasset]:
                return stdasset
        return asset
    def _makepair(self, f, t):
        return "%s%s" % (self._currencyMap(f), self._currencyMap(t))
    def _nonce(self):
        nonce = self.confgetint('lastnonce', fallback=0) + 1
        # Time based alternative
        #nonce = int(1000*time.time())
        nonce = int(time.time()*1000)
        return nonce
    async def _signedpost(self, url, data):
        urlpath = urllib.parse.urlparse(url).path.encode('UTF-8')
        data['nonce'] = self._nonce()
        datastr = urllib.parse.urlencode(data)

        # API-Sign = Message signature using HMAC-SHA512 of (URI
        # path + SHA256(nonce + POST data)) and base64 decoded
        # secret API key
        noncestr = str(data['nonce'])
        datahash = (noncestr + datastr).encode('UTF-8')
        message = urlpath + hashlib.sha256(datahash).digest()
        msgsignature = hmac.new(base64.b64decode(self.confget('apisecret').encode('UTF-8')),
                                message,
                                hashlib.sha512)
        sign = base64.b64encode(msgsignature.digest()).replace(b'\n', b'')
        headers = {
            'API-Key' : self.confget('apikey'),
            'API-Sign': sign,
            }
        body, response = await self._post(url, body=datastr, headers=headers)
        return body, response
    async def _query_private(self, method, args):
        url = "%s%s" % (self.privatebaseurl, method)
        body, response = await self._signedpost(url, args)
        j = simplejson.loads(body.decode('UTF-8'), use_decimal=True)
        #print(j)
        if 0 != len(j['error']):
            exceptionmap = {
                'EGeneral:Internal error' : Exception,
                'EAPI:Invalid nonce' : Exception,
                'EOrder:Insufficient funds' : Exception,
            }
            e = Exception
            if j['error'][0] in exceptionmap:
                e = exceptionmap[j['error'][0]]
            raise e('unable to query %s: %s' % (method, j['error']))
        return j['result']
    async def _query_public(self, method, args):
        url = "%s%s" % (self.baseurl, method)
        
        if args:
            url = "%s?%s" % (url, urllib.parse.urlencode(args))
        j, r = await self._jsonget(url)
        return j
    async def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.wantedpairs
        #await self._fetchTicker(pairs)
        await self._fetchOrderbooks(pairs)

    async def _fetchOrderbooks(self, pairs):
        now = time.time()
        res = {}
        for pair in pairs:
            pairstr = self._makepair(pair[0], pair[1])
            j = await self._query_public('Depth', {'pair' : pairstr})
            #print(j)
            o = Orderbook()
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                # For some strange reason, some orders have timestamps
                # in the future.  This is reported to Kraken Support
                # as request 1796106.
                for order in j['result'][pairstr][side]:
                    #print("Updating %s", (side, order), now - order[2])
                    o.update(oside, Decimal(order[0]), Decimal(order[1]), order[2])
                #print(o)
            self.updateOrderbook(pair, o)

    async def _fetchTicker(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pairstr= self._makepair(f, t)
            #print(pairstr)
            j = await self._query_public('Ticker', {'pair' : pairstr})
            if 0 != len(j['error']):
                raise Exception(j['error'])
            ask = Decimal(j['result'][pairstr]['a'][0])
            bid = Decimal(j['result'][pairstr]['b'][0])
            self.updateRates(p, ask, bid, None)
            res[p] = self.rates[p]
        return res

    class KrakenTrading(Trading):
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
            """Round the given price to the nearest accepted value.  Kraken limit
            the number of digits for a given marked price and reject
            orders with more digits in the proposed price.

            """
            digits = {
                (('BTC','EUR'),Orderbook.SIDE_ASK): Decimal('.1'),
                (('BTC','EUR'),Orderbook.SIDE_BID): Decimal('.1'), # FIXME value is guessed
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
            if self._lastbalance is not None and \
               self._lastbalance['timestamp'] + 10 > time.time():
                return self._lastbalance
            assets = await self.service._query_private('Balance', {})
            #print("Balance:", assets)
            res = { 'balance' : {}, 'available': {} }
            for asset in assets.keys():
                c = self.service._revCurrencyMap(asset)
                res['balance'][c] = Decimal(assets[asset])
                # FIXME figure out how to find the amount available
                res['available'][c] = Decimal(assets[asset])
            self._lastbalance = res
            self._lastbalance['timestamp'] = time.time()
            return res
        async def placeorder(self, marketpair, side, price, volume, immediate=False):
            # Invalidate balance cache
            self._lastbalance = None
            pairstr = self.service._makepair(marketpair[0], marketpair[1])
            if price is None:
                ordertype = 'market'
            else:
                ordertype = 'limit'
            type = {
                    Orderbook.SIDE_ASK : 'sell',
                    Orderbook.SIDE_BID : 'buy',
            }[side]
            args = {
                'pair' : pairstr,
                'type' : type,
                'ordertype' : ordertype,
                'price' : price,
                'volume' : volume,
#                'oflags' : ,
#                'starttm' : ,
            }
            res = await self.service._query_private('AddOrder', args)
            print(res)
            txids = res['txid']
            txdesc = res['descr']
            return txids
        async def cancelorder(self, marketpair, orderref):
            # Invalidate balance cache
            self._lastbalance = None
            args = {'txid' : orderref}
            res = await self.service._query_private('CancelOrder', args)
            return res
        async def cancelallorders(self, marketpair=None):
            raise NotImplementedError()
        async def orders(self, marketpair = None):
            """Return the currently open orders in standardized format."""

            args = {
                'trades' : True,
#                'userref' : ,
            }
            orders = await self.service._query_private('OpenOrders', args)
            """ Example output from the service
{
  'open': {
    'OTQATO-TUBHG-J2WJNK': {'userref': 0,
      'vol_exec': '0.00000000',
      'limitprice': '0.00000',
      'opentm': Decimal('1538127677.0559'),
      'expiretm': 0,
      'refid': None,
      'status': 'open',
      'stopprice': '0.00000',
      'price': '0.00000',
      'oflags': 'fciq',
      'fee': '0.00000',
      'descr': {
        'price': '8575.9',
        'order': 'sell 0.00200000 XBTEUR @ limit 8575.9',
        'close': '',
        'ordertype': 'limit',
        'type': 'sell',
        'pair': 'XBTEUR',
        'leverage': 'none',
        'price2': '0'
     },
     'starttm': 0,
     'vol': '0.00200000',
     'cost': '0.00000',
     'misc': ''
    }
  }
}

"""
            res = {}
            for id in orders['open'].keys():
                order = orders['open'][id]

                type = { 'buy': 'bid', 'sell':'ask'}[order['descr']['type']]
                pairstr = order['descr']['pair']
                # Why on earth is kraken not returning the X/Z-style
                # pair names here?  Injecting and hoping for the best. :/
                pair = (self.service._revCurrencyMap('X'+pairstr[0:3]),
                        self.service._revCurrencyMap('Z'+pairstr[3:]))
                #print(pair)
                volume = Decimal(order['vol'])
                price = Decimal(order['descr']['price'])
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
                    res[pair]['ask'] = sorted(res[pair]['ask'], key=lambda k: k['price'], reverse=True)
                if 'bid' in res[pair]:
                    res[pair]['bid'] = sorted(res[pair]['bid'], key=lambda k: k['price'])
            #print(res)
            return res
        def estimatefee(self, side, price, volume):
            """From https://www.kraken.com/help/fees, the max fee is 0.26%.

            """
            return price * volume * Decimal(0.0026)
    def trading(self):
        if self.confget('apikey', fallback=None) is None:
            return None
        if self.activetrader is None:
            self.activetrader = self.KrakenTrading(self)
        return self.activetrader

    def websocket(self):
        return self.WSClient(self)

    class WSClient(WebSocketClient):
        def __init__(self, service):
            super().__init__(service)
            self.url = "wss://ws.kraken.com"
            self.channelinfo = {}
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            #print("_on_connection_success()")
            pairs = []
            for p in self.service.ratepairs():
                pairs.append("%s/%s" % (p[0], p[1]))
            data = {
                'event': 'subscribe',
                'subscription': {
                    'name': 'book',
                    'depth': 1000, # One of 10, 25, 100, 500, 1000
                },
                'pair': pairs,
            }
            self.send(data)
            pass
        def symbols2pair(self, symbol):
            symbolmap = {
                'XBT': 'BTC',
                'XDG': 'DOGE',
                'XLM': 'STR',
                }
            pair = symbol.split('/')
            if pair[0] in symbolmap:
                pair[0] = symbolmap[pair[0]]
            return tuple(pair)
        def _on_message(self, msg):
            m = simplejson.loads(msg, use_decimal=True)
            #print()
            #print(m)
            if dict == type(m):
                # status/heartbeat
                if 'event' in m:
                    if 'subscriptionStatus' == m['event']:
                        channel = m['channelID']
                        pair = self.symbols2pair(m['pair'])
                        self.channelinfo[channel] = { 'pair': pair}
                    elif 'heartbeat' == m['event']:
                        pass
                    elif 'systemStatus' == m['event']:
                        pass
            elif list == type(m):
                channel = m[0]
                pair = self.channelinfo[channel]['pair']
                updates = list(m[1].keys())
                #print("channel update:", updates, pair)
                for update in updates:
                    if update in ('as', 'bs'):
                        o = Orderbook()
                        for side in ('as', 'bs'):
                            oside = {
                                'as' : o.SIDE_ASK,
                                'bs' : o.SIDE_BID,
                            }[side]
                            for e in m[1][side]:
                                o.update(oside, Decimal(e[0]), Decimal(e[1]), float(e[2]))
                        self.service.updateOrderbook(pair, o)
                    elif update in ('a', 'b'):
                        o = self.service.orderbooks[pair].copy()
                        for side in ('a', 'b'):
                            oside = {
                                'a' : o.SIDE_ASK,
                                'b' : o.SIDE_BID,
                            }[side]
                            if side in m[1]:
                                for e in m[1][side]:
                                    price = Decimal(e[0])
                                    if '0.00000000' == e[1]:
                                        try:
                                            o.remove(oside, price)
                                        except KeyError as e:
                                            raise ValueError('asked to remove non-existing %s order %s' % (oside, price))
                                    else:
                                        volume = Decimal(e[1])
                                        o.update(oside, price, volume, float(e[2]))
                        self.service.updateOrderbook(pair, o)
            return
            if False:
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


class TestKraken(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Kraken(['BTC', 'EUR', 'NOK', 'USD'])
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
    async def checkFetchTicker(self):
        res = await self.s._fetchTicker()
        pair = ('BTC', 'EUR')
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
        bidamount = Decimal('0.01')
        b = await t.balance()
        if pair[1] in b['available']:
            balance = b['available'][pair[1]]
        if balance > bidamount * bidprice:
            print("placing buy order %s %s at %s %s" % (bidamount, pair[0], bidprice, pair[1]))
            txs = await t.placeorder(pair, Orderbook.SIDE_BID,
                                     bidprice, bidamount, immediate=False)
            print("placed orders: %s" % txs)
            for tx in txs:
                print("cancelling order %s" % tx)
                j = await t.cancelorder(pairstr, tx)
                print("done cancelling: %s" % str(j))
                self.assertTrue('count' in j and j['count'] == 1)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (bidamount, pair[1], balance))

        balance = 0
        askamount = Decimal('0.001')
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
                j = await t.cancelorder(pairstr, tx)
                print("done cancelling: %s" % str(j))
                self.assertTrue('count' in j and j['count'] == 1)
        else:
            print("unable to place %s %s order, balance only had %s"
                  % (askamount, pair[0], balance))

        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

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

    def testRoundingPrices(self):
        t = self.s.trading()
        pair = ('BTC', 'EUR')
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.1')))
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.11')))
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_ASK, Decimal('0.17')))

        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.1')))
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.11')))
        self.assertEqual(Decimal('0.1'),
                    t.roundtovalidprice(pair, Orderbook.SIDE_BID, Decimal('0.17')))

if '__main__' == __name__:
    t = TestKraken()
    unittest.main()
