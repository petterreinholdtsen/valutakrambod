# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import json
import mechanize

class Service(object):
    def __init__(self):
        self.mech = mechanize.Browser()
    def _jsonget(self, url, timeout = 30):
        self.mech.open(url, timeout = timeout)
        response = self.mech.response()
        jsonstr = response.read()
        j = json.loads(jsonstr.decode('UTF-8'))
        return j, response
    def servicename(self):
        raise NotImplementedError()
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
        """
Return list of currency exchange rates, on this form

[
   {
      "from" : "USD",
      "to" : "BTC",
      "ask" : 1.121,
      "bid" : 1.120,
      "when" : ?,
   },
   ...
]

The relationship is such that such that

  fromval (in currency 'from') = rate * toval (in currency 'to')

This method must be implemented in each service.

"""
        raise NotImplementedError()
        
