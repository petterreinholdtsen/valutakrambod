# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import datetime
import dateutil
import re
import unittest

from decimal import Decimal
from lxml import etree
from pytz import UTC

from valutakrambod.services import Service

class Norgesbank(Service):
    """Query the exchange rates from Norges Bank.  The rates are updated
daily.  See also https://www.norges-bank.no/RSS/.

    """
    epoch = datetime.datetime(1970, 1, 1, tzinfo=UTC)
    baseurl = "https://www.norges-bank.no/"

    def servicename(self):
        return "Norgesbank"

    def ratepairs(self):
        return [
            ('USD', 'NOK'),
            ('EUR', 'NOK'),
            ]
    def datestr2epoch(self, datestr):
        when = dateutil.parser.parse(datestr)
        return (when - self.epoch).total_seconds()
    def fetchRates(self, pairs = None):
        if pairs is None:
            pairs = self.ratepairs()
        eururl = '%sRSS/Euro-EUR---dagens-valutakurs-fra-Norges-Bank/' % self.baseurl
        usdurl = '%sRSS/Amerikanske-dollar-USD---dagens-valutakurs-fra-Norges-Bank/' % self.baseurl
        res = {}
        for pair in pairs:
            url = {
                ('EUR', 'NOK') : eururl,
                ('USD', 'NOK') : usdurl,
            }[pair]
            #print(url)
            r = self._get(url)
            rss =  etree.fromstring(r.body)
            item = rss.xpath('/rss/channel/item')[0]
            title = item.xpath("./title/text()")[0]
            # Note, pubdate from this source can not be trusted.  It
            # was seen to move back in time, from 17:00 GMT to 03:00
            # GMT, and is ignored because of this.
            pubdate = item.xpath("./pubDate/text()")[0]
            m = re.match("1 %s = ([0-9.]+) NOK (\d{4}-\d{2}-\d{2}) Norges Banks midtkurs" % pair[0], title)
            if m:
                r = Decimal(m.group(1))
                # Hardcode 16:00 CET based on information from
                # https://www.norges-bank.no/Statistikk/Valutakurser/
                when = self.datestr2epoch("%s 16:00 CET" % m.group(2))
                #print(title, pubdate, when)
                self.updateRates(pair, r, r, when)
                res[pair] = self.rates[pair]
            else:
                raise ValueError("unexpected RSS returned")
        return res

    def websocket(self):
        """Exchange rates do not provide websocket API 2018-06-27."""
        return None

class TestNorgesbank(unittest.TestCase):
    """
Run simple self test.
"""
    def setUp(self):
        self.s = Norgesbank()
    def testCurrentRates(self):
        res = self.s.currentRates()
        for pair in self.s.ratepairs():
            self.assertTrue(pair in res)
            ask = res[pair]['ask']
            bid = res[pair]['bid']
            self.assertTrue(ask >= bid)
            spread = 100*(ask/bid-1)
            self.assertTrue(spread >= 0 and spread < 5)

if __name__ == '__main__':
    t = TestNorgesbank()
    unittest.main()
