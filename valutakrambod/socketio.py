# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

"""A bare minimum SocketIO client, based on reverse engineering the
Paymium protocol and information found on
https://socket.io/docs/server-api/ and
https://github.com/socketio/engine.io-protocol

"""

from tornado import escape
from tornado import gen
from tornado import httpclient
from tornado import httputil
from tornado import ioloop
from tornado import websocket

import time
import simplejson

import valutakrambod.websocket

class SocketIOClient(valutakrambod.websocket.WebSocketClient):
    """Base for SocketIO websocket socket clients.
    """
    def __init__(self, service, *,
                 connect_timeout=valutakrambod.websocket.DEFAULT_CONNECT_TIMEOUT,
                 request_timeout=valutakrambod.websocket.DEFAULT_REQUEST_TIMEOUT):
        # FIXME figure out how to pass all args to the super __init__.
        super().__init__(service,
                         connect_timeout=connect_timeout,
                         request_timeout=request_timeout,
        )
        self.pinginterval = 0
    def subscribe(self, channel):
        self.send("40%s" % channel)
    def _ping(self, first=False):
        if 0 == self.pinginterval:
            return
        if not first:
            self.send("2probe")
        # schedule next ping
        loop = ioloop.IOLoop.current()
        self._ping_ref = loop.call_later(self.pinginterval, self._ping)
    
    def _on_message(self, msg):
        if self.trace:
            print("received '%s'" % msg)
        if msg is None:
            return

        type = msg[0]
        if "0" == type:
            j = simplejson.loads(msg[1:])
            if self.trace:
                print(j)
            self.pinginterval = j['pingInterval'] / 1000
            self._ping(first=True)
            return
        elif "2" == type: # ping
            self.send("3" + msg[1:])
            return
        elif "3" == type: # pong, reply to pin
            return
        elif "4" == type:
            dtype = msg[1]
            if '0' == dtype: # FIXME what is this?  subscribe confirm?
                pass
            elif '2' == dtype:
                channel, data = msg[2:].split(',', 1)
                if self.trace:
                    print("channel '%s' data '%s'" % (channel, data))
                events = simplejson.loads(data, use_decimal=True)
                self._on_event(channel, events)
            else:
                self.service.logerror("received unhandled SocketIO data type %s" % dtype)
                    
        else:
            self.service.logerror("received unhandled SocketIO type %s" % type)
    def _on_event(self, channel, events):
        """This is called when a set of new events is available from the server.
        :param str channel: the channel for the event
        :param list events: the set of events received
        """

        if self.trace:
            print("_on_events('%s', '%s')" % (channel, events))
        pass
