# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from BTCtrader.services import Service

class Bitstamp(Service):
    """
Query the Bitstamp API.  Documentation is available from
https://www.bitstamp.com/help/api#general-usage .
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
        if pairs is None:
            pairs = self.ratepairs()
        res = []
        for p in pairs:
            f = p[0]
            t = p[1]
            url = "%sticker/btc%s/" % (self.baseurl, t.lower())
            #print(url)
            # this call raise HTTP error with invalid currency.
            # should we catch it?
            j, r = self._jsonget(url)
            #print(j)
            ask = j['ask']
            bid = j['bid']
            res.append({
                'from': f,
                'to': t,
                'ask': ask,
                'bid': bid,
                'when': j['timestamp'],
            })
        return res

def main():
    """
Run simple self test.
"""
    s = Bitstamp()
    print(s.currentRates())

if __name__ == '__main__':
    main()
#    my $req = new HTTP::Request
#        "GET","https://www.bitstamp.net/api/v2/ticker/btc$cur/";
#    my $res = $ua->request($req);
#    $tick = eval {$j->decode($res->content)} if($res->code == 200);
#    return $tick if ($tick);
