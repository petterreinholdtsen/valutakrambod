# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from tornado import ioloop

from . import *

def BTCrates():
    collectors = []
    for e in valutakrambod.service.knownServices():
        s = e()
        print(s.servicename() + ":")
        c = s.currentRates()
        s = s.websocket()
        if s:
            collectors.append(s)
        for p in c.keys():
            print("%s-%s: %s" % (p[0], p[1], c[p]))
    for c in collectors:
        c.connect()
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass
    for c in collectors:
        c.close()

if __name__ == '__main__':
    BTCrates()
