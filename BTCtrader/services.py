# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json
import time
from operator import neg

from sortedcontainers.sorteddict import SortedDict
from tornado import httpclient

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
    def update(self, side, price, volume):
        table = {
            self.SIDE_ASK : self.ask,
            self.SIDE_BID : self.bid,
        }[side]
        table[price] = volume
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

class Service(object):
    def __init__(self):
        self.http_client = httpclient.HTTPClient()
        self.rates = {}
        self.orderbooks = {}
        self.subscribers = []
    def _jsonget(self, url, timeout = 30):
        req = httpclient.HTTPRequest(url,
                          "GET",
                          request_timeout=timeout,
        )
        response = self.http_client.fetch(req)
        j = json.loads(response.body.decode('UTF-8'))
        return j, response
    def servicename(self):
        raise NotImplementedError()
    def subscribe(self, callback):
        pass
    def updateRates(self, pair, ask, bid, when):
        now = time.time()
        self.rates[pair] = {
            'ask':  ask,
            'bid':  bid,
            'when': when,
            'stored': now,
        }
        self.stats(pair)

    def updateOrderbook(self, pair, book):
        self.orderbooks[pair] = book
        print("ask len %d" % len(book.ask.keys()))
        print("bid len %d" % len(book.bid.keys()))
        self.updateRates(pair,
                         book.ask.peekitem(0)[0],
                         book.bid.peekitem(0)[0],
                         book.lastupdate)

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
    def currentrates(self):
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
        raise NotImplementedError()

    def websocket(self):
        """Return a websocket client object.  Return None if no websocket API
is available.

        """
        return None
