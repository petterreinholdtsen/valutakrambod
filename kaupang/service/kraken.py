# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from kaupang.services import Service

class Kraken(Service):
    """
Query the Kraken API.  Documentation is available from
https://www.kraken.com/help/api#general-usage .
"""
    keymap = {
        'BTC' : 'XBT',
        }
    baseurl = "https://api.kraken.com/0/public/"
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
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            pair="X%sZ%s" % (self._currencyMap(f), self._currencyMap(t))
            #print(pair)
            url = "%sTicker?pair=%s" % (self.baseurl, pair)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            if 0 != len(j['error']):
                raise Error(j['error'])
            ask = float(j['result'][pair]['a'][0])
            bid = float(j['result'][pair]['b'][0])
            self.updateRates(p, ask, bid, None)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Kraken do not provide websocket API 2018-06-27."""
        return None

def main():
    """
Run simple self test.
"""
    s = Kraken()
    print(s.currentRates())

if __name__ == '__main__':
    main()
