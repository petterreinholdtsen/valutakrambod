# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from kaupang.services import Service

class MiraiEx(Service):
    """Query the Mirai Exchange API.  Based on documentation found in
https://gist.github.com/mikalv/7b4f44a34fd48e0b87877c1771903b0a/ .

    """
    baseurl = "http://miraiex.com/api/v1/"

    def servicename(self):
        return "MiraiEx"

    def ratepairs(self):
        return [
            ('BTC', 'NOK'),
            ('ANC', 'BTC'),
            ('GST', 'BTC'),
            ('LTC', 'BTC'),
            ]
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        url = "%smarkets" % self.baseurl
        #print(url)
        j, r = self._jsonget(url)
        #print(j)
        res = {}
        for market in j:
            pair = (market['id'][:3], market['id'][3:])
            #print(pair)
            if pair in pairs:
                self.updateRates(pair,
                                 float(market['ask']),
                                 float(market['bid']),
                                 None)
                res[pair] = self.rates[pair]
        return res

    def websocket(self):
        """Not known of Mirai provide websocket API 2018-07-02."""
        return None

def main():
    """
Run simple self test.
"""
    s = MiraiEx()
    print(s.currentRates())

if __name__ == '__main__':
    main()
