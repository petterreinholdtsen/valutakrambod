# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json
import time

from tornado import ioloop

from kaupang.services import Orderbook
from kaupang.services import Service
from kaupang.websocket import WebSocketClient

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
            #print(m)
            o = Orderbook()
            for side in ('asks', 'bids'):
                oside = {
                    'asks' : o.SIDE_ASK,
                    'bids' : o.SIDE_BID,
                }[side]
                for e in m[side]:
                    o.update(oside, e['price_int'] / 100000, e['price_int'] / 100000 )
            # FIXME setting our own timestamp, as there is no
            # timestamp from the source.  Asked bl3p to set one in
            # email sent 2018-06-27.
            #o.setupdated(time.time())
            self.service.updateOrderbook(self._marketmap[m['marketplace']], o)
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
