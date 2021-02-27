# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import configparser
import random
import time
import tornado.ioloop
import unittest
import uuid

from decimal import Decimal
from os.path import expanduser

from valutakrambod.services import Service
from valutakrambod.services import Orderbook
from valutakrambod.services import Trading

# Use global counter to name the dummy services using a number
last = -1

def random_decimal():
    return Decimal("%f" % random.random())

class DummyService(Service):
    """Service useful for debugging.  Provide randomly generated orderbook
around a predefined price, with a predefined spread.

    """
    def __init__(self, currencies=None):
        global last
        super().__init__(currencies)
        self.pricecenter = Decimal('5000.0')
        self.spread = Decimal('0.01')
        self.n = last + 1
        self.lasttime = time.time()
        last = self.n
        #print("Created service %d" % self.n)
    def servicename(self):
        return "DummyService%d" % self.n

    def ratepairs(self):
        return [
#            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
#            ('BTC', 'USD'),
            ]
    async def fetchRates(self, pairs = None):
        print("Fetching rates")
        if pairs is None:
            pairs = self.wantedpairs
        self._fetchOrderbooks(pairs)

    def _fetchOrderbooks(self, pairs):
        print("Generating orderbook rates")
        offset = 20
        self.pricecenter = \
            self.pricecenter + offset * (random_decimal() - Decimal('0.5'))
        self.spread = Decimal('0.01') * random_decimal()
        now = time.time()
        for pair in pairs:
            o = Orderbook()
            for side, direction in ((o.SIDE_ASK, 1), (o.SIDE_BID, -1)):
                depth=10
                for i in range(depth):
                    randombook = True
                    if randombook:
                        price = self.pricecenter \
                                + i * direction * random_decimal() \
                                + self.spread / 2 * direction * self.pricecenter
                        price = price.quantize(Decimal('.001'))
                        # Ensure we avoid zero amount
                        amount = 2 * random_decimal() + Decimal('0.00001')
                    else:
                        price = depth + i * direction
                        amount = 1
                    when = now - (now - self.lasttime) * random.random()
                    o.update(side, Decimal(price), Decimal(amount), when)
            self.updateOrderbook(pair, o)
        self.lasttime = now

    def websocket(self):
        """Dummy service do not provide websocket API."""
        return None

    class DummyServiceTrading(Trading):
        """Fake trade exchange to test the trade machinery.  It will buy/sell
according to the current orderbook when an order is placed.  New
orders in the orderbook is generated when asking for an updated
orderbook/ticker.

        """
        def __init__(self, service):
            super().__init__(service)
            self._orders = {}
            self._closedorders = {}
            self.verbose = False
            # Fill up the accounts with some content
            self._balance = {}
            for pair in service.ratepairs():
                if 0 == service.n % 2:
                    self.log("Service %s started with 1 %s" % (service.servicename(),
                                                                pair[0]))
                    self._balance[pair[0]] = Decimal('1') # BTC
                    self._balance[pair[1]] = Decimal('0') # EUR
                else:
                    self.log("Service %s started with 10 %s" % (service.servicename(),
                                                                pair[1]))
                    self._balance[pair[0]] = Decimal('0') # BTC
                    self._balance[pair[1]] = Decimal('10') # EUR
                #self._balance[pair[0]] = Decimal('1') # BTC
                #self._balance[pair[1]] = Decimal('10') # EUR
        def log(self, msg):
            if self.verbose:
                print(msg)
        async def balance(self):
            # Return a deep copy, to make sure clients do not modify
            # the currenct balance by mistake.
            return self._balance.copy()
        async def placeorder(self, pair, side, price, volume, immediate=False):
            self.log("Balance at start: %s" % self._balance)
            orderref = uuid.uuid1()
            self._orders[orderref] = (pair, side, price, volume, immediate)
            if pair[0] not in self._balance:
                self._balance[pair[0]] = Decimal(0)
            if pair[1] not in self._balance:
                self._balance[pair[1]] = Decimal(0)
            if Orderbook.SIDE_BID == side:
                self.log("Trying to buy %s %s for %s %s" % (
                    volume, pair[0], price, pair[1],
                ))
                volumeleft = volume
                book = self.service.orderbooks[pair]
                totalcost = Decimal(0.0)
                #print("Askbook1:", book.ask)
                moneyleft = self._balance[pair[1]]
                # Delay removal to make sure keys() return all the keys in the set
                toremove = []
                ordercount = 0
                for orderprice in book.ask.keys():
                    #print("ordercount %d" % ordercount)
                    ordercount = ordercount + 1
                    if price is None or orderprice < price:
                        if book.ask[orderprice] <= volumeleft:
                            self.log("buying entire order %s @ %s" % (book.ask[orderprice], orderprice))
                            # Buy the entire offer and remove it
                            cost = book.ask[orderprice] * orderprice
                            totalcost = totalcost + cost \
                                + self.estimatefee(side, orderprice,
                                                   book.ask[orderprice])
                            volumeleft = volumeleft - book.ask[orderprice]
                            if moneyleft >= cost:
                                moneyleft = moneyleft - cost
                            else:
                                self.log("not enough money to pay the cost %s > %s" % (cost , moneyleft))
                                break
                            toremove.append(orderprice)
                            #book.remove(book.SIDE_ASK, orderprice)
                            # FIXME schedule notification?
                        else:
                            self.log("buying part of order %s @ %s" % (
                                book.ask[orderprice], orderprice
                            ))
                            # Only buy part of this offer, replace its
                            # volume with what is left.
                            cost = volumeleft * orderprice
                            # Only use the money you got
                            if moneyleft >= cost:
                                moneyleft = moneyleft - cost
                                book.ask[orderprice] = book.ask[orderprice] - volumeleft
                                volumeleft = 0
                            else:
                                self.log("Ran out of money, buy less")
                                buyvolume = moneyleft / orderprice
                                moneyleft = 0
                                book.ask[orderprice] = book.ask[orderprice] - buyvolume
                                volumeleft = volumeleft - buyvolume
                                break
                    else:
                        self.log("ignoring %s count %d" % (orderprice, ordercount))
                        pass
                    if 0 == volumeleft:
                        #print("all volume found")
                        break
                for orderprice in toremove:
                    book.remove(book.SIDE_ASK, orderprice)
                self._balance[pair[0]] = self._balance[pair[0]] + \
                                         volume - volumeleft
                self._balance[pair[1]] = moneyleft
                #print("Askbook2:", book.ask)
                #print("Left:", volumeleft)
                #print("Balance %s:" % pair[0], str(self._balance[pair[0]]))
                #print("Balance %s:" % pair[1], str(self._balance[pair[1]]))
            elif Orderbook.SIDE_ASK == side:
                self.log("Trying to sell %s %s for %s %s" % (
                    volume, pair[0], price, pair[1],
                ))
                volumeleft = volume
                book = self.service.orderbooks[pair]
                totalearn = Decimal(0.0)
                #print("Bidbook1:", book.bid)
                moneyleft = self._balance[pair[0]]
                if moneyleft < volume:
                    raise Exception("not enough balance to sell %s %s" % (
                        volume, pair[0]
                    ))
                # Delay removal to make sure keys() return all the keys in the set
                toremove = []
                ordercount = 0
                for orderprice in book.bid.keys():
                    #print("ordercount %d" % ordercount)
                    ordercount = ordercount + 1
                    if price is None or orderprice >= price:
                        if book.bid[orderprice] < volumeleft:
                            self.log("selling everything to order %s @ %s" % (
                                book.bid[orderprice], orderprice
                            ))
                            # Sell everything to this offer and reduce or remove it
                            earn = book.bid[orderprice] * orderprice \
                                - self.estimatefee(side, orderprice,
                                                   book.bid[orderprice])
                            totalearn = totalearn + earn
                            volumeleft = volumeleft - book.bid[orderprice]
                            book.bid[orderprice] = 0
                            toremove.append(orderprice)
                            #book.remove(book.SIDE_BID, orderprice)
                            self.log("earn %s %s, volume left in order %s, want %s" % (
                                totalearn, pair[1], book.bid[orderprice], volumeleft,
                            ))
                            # FIXME schedule notification?
                        else:
                            self.log("selling part to order %s @ %s" % (
                                book.bid[orderprice], orderprice
                            ))
                            # Sell part of volume to all of this order
                            # and continue to the next, schedule the
                            # removal og this order.

                            earn =  volumeleft * orderprice
                            totalearn = totalearn + earn
                            book.bid[orderprice] = book.bid[orderprice] - volumeleft
                            volumeleft = Decimal(0)
                            self.log("earn %s, left in order %s" % (totalearn, book.bid[orderprice]))
                            #toremove.append(orderprice)
                    else:
                        self.log("ignoring %s count %d" % (orderprice, ordercount))
                        pass
                    if 0 == volumeleft:
                        self.log("all volume found")
                        break
                for orderprice in toremove:
                    book.remove(book.SIDE_BID, orderprice)
                self._balance[pair[1]] = self._balance[pair[1]] + totalearn
                self._balance[pair[0]] = self._balance[pair[0]] - volume + volumeleft
                #print("Bidbook2:", book.bid)
                #print("Left:", volumeleft)
                #print("Balance %s:" % pair[0], str(self._balance[pair[0]]))
                #print("Balance %s:" % pair[1], str(self._balance[pair[1]]))
            self.log("Balance when done: %s" % self._balance)
            return orderref
        def cancelorder(self, pair, orderref):
            if orderref in self._orders:
                info = self._orders[orderref]
                del self._orders[orderref]
                return info
            return None
        def cancelallorders(self):
            self._orders.clear()
        def orders(self, market=None):
            return self._orders
        def closedorders(self, marked=None):
            raise NotImplementedError()
        def estimatefee(self, side, price, volume):
            fee = price * volume * Decimal('0.0026') + Decimal('0.01')
            #print('returned fee %s' % fee)
            return fee
    def trading(self):
        if self.activetrader is None:
            self.activetrader = self.DummyServiceTrading(self)
        return self.activetrader

class TestDummyService(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        # Make sure we get the same servicename every time.
        global last
        last = -1
        self.s = DummyService()
        # Load some rates to have them ready
        self.s._fetchOrderbooks(self.s.wantedpairs)
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
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            #print("Spread:", spread)
            self.assertTrue(spread > 0 and spread < 5)
        self.ioloop.stop()
    def testCurrentRates(self):
        self.runCheck(self.checkCurrentRates)
    def checkUpdates(self):
        from tornado import ioloop
        def printUpdate(service, pair, changed):
            if False:
                print(pair,
                      service.rates[pair]['ask'],
                      service.rates[pair]['bid'],
                      time.time() - service.rates[pair]['when'],
                      time.time() - service.rates[pair]['stored'],
                )
            self.updates += 1
            self.ioloop.stop()
        self.s.subscribe(printUpdate)
        self.s.periodicUpdate(3)
    def testUpdates(self):
        self.updates = 0
        self.runCheck(self.checkUpdates, timeout=10)
        self.assertTrue(0 < self.updates)

    async def checkTradingConnection(self):
        # Unable to test without API access credentials in the config
        if self.s.confget('apikey', fallback=None) is None:
            print("no apikey found, skipping trading test")
            return
        print("trying some trades")
        t = self.s.trading()
        print(t.orders())

        b1 = await t.balance()
        #print(b1)

        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_ASK,  4070, Decimal(0.5))

        b2 = await t.balance()
        #print(b2)
        self.assertTrue(b1['BTC'] > b2['BTC'], 'sold some BTC')
        self.assertTrue(b1['EUR'] < b2['EUR'], 'bought some EUR')

        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_ASK, None, Decimal(0.5))
#        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_ASK, None, Decimal(0.5))
#
#        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_BID, None, Decimal(0.5))
        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_BID, None, Decimal(0.5))
        ref = await t.placeorder(('BTC', 'EUR'), Orderbook.SIDE_BID, 5030,   Decimal(0.5))
        b3 = await t.balance()
        #print(b3)
        self.assertTrue(b2['BTC'] < b3['BTC'], 'bought back some BTC')
        self.assertTrue(b2['EUR'] > b3['EUR'], 'sold back some EUR')

        self.assertTrue(b1['BTC'] == b3['BTC'], 'lost BTC value in the process')

        t.cancelorder('BTCEUR', ref)
        t.cancelallorders()
        self.ioloop.stop()
    def testTradingConnection(self):
        self.runCheck(self.checkTradingConnection)

if __name__ == '__main__':
    t = TestDummyService()
    unittest.main()
