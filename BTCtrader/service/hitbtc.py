# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json
import dateutil.parser
import datetime
from pytz import UTC

from tornado import ioloop

from BTCtrader.services import Service
from BTCtrader.websocket import WebSocketClient

class Hitbtc(Service):
    """
Query the Hitbtc API.
"""
    baseurl = "http://api.hitbtc.com/api/1/"
    def servicename(self):
        return "Hitbtc"

    def ratepairs(self):
        return [
            ('BTC', 'USD'),
            ]
    def _currencyMap(self, currency):
        if currency in self.keymap:
            return self.keymap[currency]
        else:
            return currency
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="%s%s" % (f, t)
            #print(pair)
            url = "%spublic/%s/ticker" % (self.baseurl, pair)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            ask = float(j['ask'])
            bid = float(j['bid'])
            self.updateRates(p, ask, bid, j['timestamp'] / 1000.0)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        return self.WSClient(self)

    class WSClient(WebSocketClient):
        epoch = datetime.datetime(1970, 1, 1, tzinfo=UTC)
        def __init__(self, service):
            super().__init__()
            self.url = "wss://api.hitbtc.com/api/2/ws"
            self.service = service
        def connect(self, url = None):
            if url is None:
                url = self.url
            super().connect(url)
        def _on_connection_success(self):
            for p in self.service.ratepairs():
                self.send({
                    "method": "subscribeTicker",
                    "params": {
                        "symbol": "%s%s" % (p[0], p[1])
                    },
                    "id": 123
                })
            pass
        def datestr2epoch(self, datestr):
            when = dateutil.parser.parse(datestr)
            return (when - self.epoch).total_seconds()
        def _on_message(self, msg):
            m = json.loads(msg)
            #print(m)
            if 'method' in m and "ticker" == m['method']:
                pair = (m['params']['symbol'][:3], m['params']['symbol'][3:])
                self.service.updateRates(pair,
                                         m['params']['ask'],
                                         m['params']['bid'],
                                         self.datestr2epoch(m['params']['timestamp']),
                )
        def _on_connection_close(self):
            pass
        def _on_connection_error(self, exception):
            pass

def main():
    """
Run simple self test.
"""
    s = Hitbtc()
    print(s.currentRates())

    c = s.websocket()
    c.connect()
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        c.close()

if __name__ == '__main__':
    main()
