# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Bitpay(Service):
    """
Query the Bitpay API.  This API do not distingquish ask and pay, so
those values are identical.

Documentation is available from ? .
"""
    baseurl = "https://bitpay.com/rates/"
    def servicename(self):
        return "Bitpay"

    def ratepairs(self):
        # FIXME get list dynamically?
        return [
            ('BTC', 'NOK'),
            ('BTC', 'EUR'),
            ]
    def currentRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        res = []
        for p in pairs:
            f = p[0]
            t = p[1]
            url = "%s%s" % (self.baseurl, t)
            #print(url)
            j, r = self._jsonget(url)
            #print(j)
            if 'error' in j:
                raise Error(j['error'])
            ask = bid = j['data']['rate']
            res.append({
                'from': f,
                'to': t,
                'ask': ask,
                'bid': bid,
                'when': None,
            })
        return res

def main():
    """
Run simple self test.
"""
    s = Bitpay()
    print(s.currentRates())

if __name__ == '__main__':
    main()
