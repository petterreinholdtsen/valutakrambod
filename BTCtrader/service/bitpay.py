# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Bitpay(Service):
    """
Query the Bitpay API.  This API do not provide both ask and pay, so
those values are set to be identical.

Documentation is available from https://bitpay.com/api .
"""
    baseurl = "https://bitpay.com/rates/"
    def servicename(self):
        return "Bitpay"

    def ratepairs(self):
        # FIXME get list dynamically?
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ('BTC', 'USD'),
            ]
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = {}
        for p in pairs:
            f = p[0]
            t = p[1]
            url = "%s%s" % (self.baseurl, t)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            if 'error' in j:
                raise Error(j['error'])
            rate = j['data']['rate']
            self.updateRates(p, rate, rate, None)
            res[p] = self.rates[p]
        return res

    def websocket(self):
        """Bitpay do not provide websocket API 2018-06-27."""
        return None

def main():
    """
Run simple self test.
"""
    s = Bitpay()
    print(s.currentRates())

if __name__ == '__main__':
    main()
