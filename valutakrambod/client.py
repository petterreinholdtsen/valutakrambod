# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import functools
import tornado.ioloop

from . import *

class SimpleClient(object):
    def __init__(self):
        self.services = []
        self.streams = []
        pass
    def newdata(self, service, pair, changed):
        print("%-15s %s-%s: %8.3f %8.3f" % (
            service.servicename(),
            pair[0],
            pair[1],
            service.rates[pair]['ask'],
            service.rates[pair]['bid'])
        )
    async def refresh(self, service):
        await service.fetchRates(service.wantedpairs)
    def run(self):
        self.ioloop = tornado.ioloop.IOLoop.current()
        self.services = valutakrambod.service.knownServices()
        for e in self.services:
            service = e()
            service.subscribe(self.newdata)
            stream = service.websocket()
            if stream:
                self.streams.append(stream)
            else:
                # Fetch information from non-streaming services immediately
                self.ioloop.call_later(len(self.services),
                                       functools.partial(self.refresh, service))
                # as well as regularly
                service.periodicUpdate(60)
        for stream in self.streams:
            stream.connect()
        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            print("Interrupted by keyboard, closing all connections.")
            pass
        for stream in self.streams:
            stream.close()

def BTCrates():
    client = SimpleClient()
    client.run()

if __name__ == '__main__':
    BTCrates()
