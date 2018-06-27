# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json
import time
from tornado import httpclient

class Service(object):
    def __init__(self):
        self.http_client = httpclient.HTTPClient()
        self.rates = {}
    def _jsonget(self, url, timeout = 30):
        req = httpclient.HTTPRequest(url,
                          "GET",
                          request_timeout=timeout,
        )
        response = self.http_client.fetch(req)
        j = json.loads(response.body.decode('UTF-8'))
        return j, response
    def servicename(self):
        raise NotImplementedError()
    def updateRates(self, pair, ask, bid, when):
        now = time.time()
        self.rates[pair] = {
            'ask':  ask,
            'bid':  bid,
            'when': when,
            'stored': now,
        }
        if when:
            age = now - when
        else:
            age = None
        print(pair, self.rates[pair]['ask'], self.rates[pair]['bid'], self.servicename(), age)
    def ratepairs(self):
        """
Return a list of touples with pair of currency codes the
service provide currency exchange rates for, on this form:

[
  ('BTC', 'USD'),
  ('BTC', 'EUR'),
]
"""
        raise NotImplementedError()
    def currentrates(self):
        """Return list of currency exchange rates, on this form

{
  ("BTC", "USD") : {
      "ask" : 1.121,
      "bid" : 1.120,
      "when" : 1530010880.037,
   },
   ...
]

The currency code values are pairs with (from, to). The relationship
is such that such that

  fromval (in currency 'from') = rate * toval (in currency 'to')

This method must be implemented in each service.

        """
        raise NotImplementedError()

    def websocket(self):
        """Return a websocket client object.  Return None if no websocket API
is available.

        """
        return None
