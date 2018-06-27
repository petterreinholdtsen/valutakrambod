# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json

from tornado import ioloop

from BTCtrader.services import Service
from BTCtrader.websocket import WebSocketClient

class Bl3p(Service):
    """
Query the Bl3p API.  Documentation is available from
https://bl3p.eu/api .
"""
    baseurl = "https://api.bl3p.eu/1/"
    def servicename(self):
        return "Bl3p"

    def ratepairs(self):
        return [
            ('LTC', 'EUR'),
            ('BTC', 'EUR'),
            ]

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
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%s%s/ticker" % (self.baseurl, pair)
            #print url
            (j, r) = self._jsonget(url)
            #print(r.code)
            if 200 != r.code:
                raise Error()
            #print(j)
            ask = j['ask']
            bid = j['bid']
            self.updateRates(p, ask, bid, int(j['timestamp']))
            res[p] = self.rates[p]
        return res

    class WSClient(WebSocketClient):
        _marketmap = {
            'BTCEUR' : ('BTC', 'EUR'),
            'LTCEUR' : ('LTC', 'EUR'),
        }
        def __init__(self, service):
            super().__init__()
            self.service = service
            self.url = "wss://api.bl3p.eu/1/BTCEUR/orderbook"
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            pass
        def _on_message(self, msg):
            m = json.loads(msg)
            # FIXME verify the order of the order book extract
            self.service.updateRates(self._marketmap[m['marketplace']],
                                     m['asks'][0]['price_int'] / 100000,
                                     m['bids'][0]['price_int'] / 100000,
                                     None)
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
    s = Bl3p()
    print(s.currentRates())

    c = s.websocket()
    c.connect()
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        c.close()

if __name__ == '__main__':
    main()
