# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json

from tornado import ioloop

from BTCtrader.services import Orderbook
from BTCtrader.services import Service
from BTCtrader.websocket import WebSocketClient

class Bitstamp(Service):
    """Query the Bitstamp API.  Documentation is available from
https://www.bitstamp.com/help/api#general-usage .

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
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    def currentRates(self, pairs = None):
        if {} == self.rates:
            self.fetchRates(pairs)
        if pairs is None:
            return self.rates
        else:
            res = {}
            #print(pairs)
            for p in pairs:
                res[p] = self.rates[p]
            return res
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            t = p[1]
            url = "%sticker/btc%s/" % (self.baseurl, t.lower())
            #print(url)
            # this call raise HTTP error with invalid currency.
            # should we catch it?
            j, r = self._jsonget(url)
            #print(j)
            ask = float(j['ask'])
            bid = float(j['bid'])
            self.updateRates(p, ask, bid, int(j['timestamp']))
            res[p] = self.rates[p]
        return res
    class WSClient(WebSocketClient):
        _channelmap = {
            'order_book' :        ('BTC', 'USD'),
            'order_book_btceur' : ('BTC', 'EUR'),
            'order_book_btcusd' : ('BTC', 'USD'),
            # FIXME add the other channels (eurusd, xrpusd, xrpeur,
            # xrpbtc, ltcusd, ltceur, ltcbtc, ethusd, etheur, ethbtc,
            # bchusd, bcheur, bchbtc)
        }
        def __init__(self, service):
            super().__init__()
            self.url = "wss://ws.pusherapp.com/app/de504dc5763aeef9ff52?protocol=6&client=js&version=2.1.2&flash=false"
            self.service = service
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            channels = [
                'order_book_btcusd',
                'order_book_btceur'
            ]
            for c in channels:
                self.send({
                    "event": "pusher:subscribe",
                    "data": {
                        "channel": c,
                    }
                })
        def _on_message(self, msg):
            m = json.loads(msg)
            #print(m)
            if 'data' == m['event']:
                o = Orderbook()
                d = json.loads(m['data'])
                for side in ('asks', 'bids'):
                    oside = {
                        'asks' : o.SIDE_ASK,
                        'bids' : o.SIDE_BID,
                    }[side]
                    for e in d[side]:
                        o.update(oside, float(e[0]), float(e[1]))
                o.setupdated(int(d['timestamp']))
                self.service.updateOrderbook(self._channelmap[m['channel']], o)
        def _on_connection_close(self):
            pass
        def _on_connection_error(self, exception):
            pass
    def websocket(self):
        return self.WSClient(self)

def main():
    """
Run simple self test.
"""
    s = Bitstamp()
    print(s.currentRates())

    c = s.websocket()
    c.connect()
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        c.close()

if __name__ == '__main__':
    main()
