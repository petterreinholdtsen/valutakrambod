# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import collections
import decimal
import simplejson
import statistics
import time
from operator import neg

from sortedcontainers.sorteddict import SortedDict
from tornado import httpclient
import tornado.ioloop

class Orderbook(object):
    SIDE_ASK = "ask"
    SIDE_BID = "bid"
    def __init__(self):
        self.ask = SortedDict()
        self.bid = SortedDict(neg)
        self.lastupdate = None
    def copy(self):
        o = Orderbook()
        o.ask = self.ask.copy()
        o.bid = self.bid.copy()
        o.lastupdate = self.lastupdate
        return o
    def update(self, side, price, volume, timestamp = None):
        table = {
            self.SIDE_ASK : self.ask,
            self.SIDE_BID : self.bid,
        }[side]
        table[price] = volume
        if timestamp and (self.lastupdate is None or timestamp > self.lastupdate):
            self.lastupdate = timestamp
    def remove(self, side, price):
        table = {
            self.SIDE_ASK : self.ask,
            self.SIDE_BID : self.bid,
        }[side]
        del table[price]
    def clear(self):
        self.ask.clear()
        self.bid.clear()
    def setupdated(self, lastupdate = None):
        if lastupdate is None:
            lastupdate = time.time()
        self.lastupdate = lastupdate

    def __str__(self):
        return "Ask: " + self.ask.__str__() + "\nBid: " + self.bid.__str__()

class Trading(object):
    def __init__(self, service):
        self.service = service
    def balance(self):
        raise NotImplementedError()
    def placeorder(self, marketpair, side, price, volume, immediate=False):
        raise NotImplementedError()
    def cancelorder(self, orderref):
        raise NotImplementedError()
    def cancelallorders(self):
        raise NotImplementedError()
    def orders(self, market= None):
        raise NotImplementedError()
    def estimatefee(self, side, price, volume):
        """Return amount of fee for a transaction selling virtual currency
volume for price.

        """
        return decimal.Decimal(0.0)

class Service(object):
    def __init__(self, currencies=None):
        self.http_client = httpclient.AsyncHTTPClient()
        self.rates = {}
        self.orderbooks = {}
        self.subscribers = []
        self.updates = {}
        self.currencies = currencies
        self.wantedpairs = None
        self.periodic = None
        self.activetrader = None
        if currencies:
            for p in self.ratepairs():
                #print(p, currencies)
                if p[0] in currencies and p[1] in currencies:
                    #print("match")
                    if self.wantedpairs is None:
                        self.wantedpairs = []
                    self.wantedpairs.append(p)
        else:
            self.wantedpairs = self.ratepairs()
        #print("Want", self.wantedpairs)
        self.errsubscribers = []
    def errsubscribe(self, callback):
        self.errsubscribers.append(callback)
    def logerror(self, msg):
        for s in self.errsubscribers:
            s(self, msg)

    def confinit(self, config):
        """Set a configparser compatible object member for use by individual
services to store configuration.

        """
        # require subclass with working servicename() to be able to
        # set the configuration member.
        if not config.has_section(self.servicename()):
            config.add_section(self.servicename())
        self._config = config
    def confget(self, key, fallback=None):
        return self._config.get(self.servicename(), key, fallback=fallback)
    def confgetint(self, key, fallback=None):
        return self._config.getint(self.servicename(), key, fallback=fallback)
    def confset(self, key, value):
        return self._config.set(self.servicename(), key, value)

    async def _get(self, url, timeout = 30):
        req = httpclient.HTTPRequest(url,
                          "GET",
                          request_timeout=timeout,
        )
        response = await self.http_client.fetch(req)
        #print("updated %s" % self.servicename())
        return response
    async def _jsonget(self, url, timeout = 30):
        response = await self._get(url, timeout=timeout)
        j = simplejson.loads(response.body.decode('UTF-8'), use_decimal=True)
        return j, response
    async def _post(self, url, body = "", headers = None):
        req = httpclient.HTTPRequest(url, "POST", body=body, headers=headers)
        response = await self.http_client.fetch(req)
        return response.body, response
    def servicename(self):
        raise NotImplementedError()
    def subscribe(self, callback):
        self.subscribers.append(callback)
    def periodicUpdate(self, mindelay = 30): # 30 seconds
        """Start periodic calls to fetchRates(), with the minimum delay in
seconds specified in as an argument.  The default update frequency is
30 seconds.  To disable periodic updates, use mindelay=0.


        """
        if mindelay < 0:
            raise ValueError('mindelay must be a positive number or zero')
        if self.periodic is not None:
            self.periodic.stop()
            self.periodic = None
        if 0 != mindelay:
            from functools import partial
            async def periodicFetchRates(self):
                try:
                    await self.fetchRates()
                except Exception as e:
                    self.logerror("%s fetchRates: %s" % (self.servicename(),
                                                         str(e)))
                    raise
            self.periodic =  tornado.ioloop.PeriodicCallback(partial(periodicFetchRates, self),
                                                             mindelay * 1000)
            self.periodic.start()

    def updateRates(self, pair, ask, bid, when):
        now = time.time()
        changed = True
        if pair in self.rates:
            old = self.rates[pair]
            if old['ask'] == ask and old['bid'] == bid and old['when'] == when:
                changed = False
            if when is not None and old['when'] is not None and old['when'] > when:
                raise Exception('received old update (%.1f < %.1f - %.1fs behind)' %
                                (when, old['when'], old['when'] - when ))

        if changed:
            if when:
                lastchange = when
            else:
                lastchange = now
            self.rates[pair] = {
                'ask':  ask,
                'bid':  bid,
                'when': when,
                'stored': now,
                'lastchange': lastchange,
            }
        else:
            self.rates[pair]['stored'] = now
            lastchange = self.rates[pair]['lastchange']
        for s in self.subscribers:
            s(self, pair, changed)
        if not pair in self.updates:
            self.updates[pair] = collections.deque(maxlen=10)
        if  lastchange and (0 == len(self.updates[pair]) or \
                            lastchange != self.updates[pair][-1]):
            self.updates[pair].append(lastchange)
#        self.stats(pair)

    def updateOrderbook(self, pair, book):
        self.orderbooks[pair] = book
        self.updateRates(pair,
                         book.ask.peekitem(0)[0],
                         book.bid.peekitem(0)[0],
                         book.lastupdate)
    def guessperiod(self, pair):
        if pair not in self.updates:
            return float('nan')
        last = None
        steps = []
        for t in self.updates[pair]:
            if last:
                steps.append(t - last)
            last = t
        if 1 < len(steps):
            now = time.time()
            period = statistics.median(steps)
#            print("Guess next update for %s is %.1f %.1f (%f)" %
#                  (self.servicename(), t + period, t + period - now, period))
            return period
        else:
            return float('nan')

    def stats(self, pair):
        print(pair,
              self.rates[pair]['ask'], self.rates[pair]['bid'],
              self.servicename())
        if pair in self.orderbooks:
            b = self.orderbooks[pair]
            bars = [1, 10, 20, 100, 1000, 2000, 50000]
            res  = [0,  0,  0,   0,    0,    0,     0]
            for side in ('ask', 'bid'):
                t = {
                    'ask' : b.ask,
                    'bid' : b.bid,
                }[side]
                barnum = 0
                amount = 0.0
                price = 0.0
                for o in t.items():
                    #print(o)
                    price = price + o[0] * o[1]
                    amount = amount + o[1]
                    #print(barnum, amount)
                    n = bars[barnum]
                    if amount > n:
                        res[barnum] = price/amount
                        barnum = barnum + 1
                        if barnum > len(bars) - 1:
                            break
                print(pair, "%s %9.4f %9.4f %9.4f %9.4f %9.4f (%s)" %
                      (side,
                       res[0],  res[1],  res[2],  res[3],  res[4],
                       self.servicename()))
            print()
    def ratepairs(self):
        """
Return a list of touples with pair of currency codes the
service provide currency exchange rates for, on this form:

[
  ('BTC', 'USD'),
  ('BTC', 'EUR'),
]
"""
        raise NotImplementedError()
    async def currentRates(self, pairs = None):
        """Return list of currency exchange rates, on this form

{
  ("BTC", "USD") : {
      "ask" : 1.121,
      "bid" : 1.120,
      "when" : 1530010880.037,
   },
   ...
]

The currency code values are pairs with (from, to). The relationship
is such that such that

  fromval (in currency 'from') = rate * toval (in currency 'to')

This method must be implemented in each service.

        """
        if {} == self.rates:
            await self.fetchRates(self.wantedpairs)
        if self.wantedpairs is None:
            return self.rates
        else:
            res = {}
            #print(pairs)
            for p in self.wantedpairs:
                res[p] = self.rates[p]
            return res

    async def fetchRates(self, pairs = None):
        raise NotImplementedError()

    def websocket(self):
        """Return a websocket client object.  Return None if no websocket API
is available.

        """
        return None
    def trading(self):
        """Returning a trading client object.  Return None if trading is not
available.

        """
        return self.activetrader
