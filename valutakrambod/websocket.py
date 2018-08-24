# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from tornado import escape
from tornado import gen
from tornado import httpclient
from tornado import httputil
from tornado import websocket

import json
import time

APPLICATION_JSON = 'application/json'

DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_REQUEST_TIMEOUT = 60

 
class WebSocketClient(object):
    """Base for web socket clients.
    """
 
    def __init__(self, service, *,
                 connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                 request_timeout=DEFAULT_REQUEST_TIMEOUT):

        self.service = service
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self.trace = False

    def connect(self, url):
        """Connect to the server.
        :param str url: server URL.
        """

        if self.trace:
            print("Connecting to %s" % url)

        headers = httputil.HTTPHeaders({'Content-Type': APPLICATION_JSON})
        request = httpclient.HTTPRequest(url=url,
                                         connect_timeout=self.connect_timeout,
                                         request_timeout=self.request_timeout,
                                         headers=headers)
        ws_conn = websocket.websocket_connect(request,
                                              callback=self._connect_callback,
                                              on_message_callback=self._read_message)

    def send(self, data):
        """Send message to the server
        :param str data: message.
        """
        if not self._ws_connection:
            raise RuntimeError('Web socket connection is closed.')
        if self.trace:
            print("Writing '%s'" % data)
        if not isinstance(data, str):
            data = escape.utf8(json.dumps(data))
        self._ws_connection.write_message(data)
        if self.trace:
            print("Wrote '%s'" % data)

    def close(self):
        """Close connection.
        """

        if not self._ws_connection:
            raise RuntimeError('Web socket connection is already closed.')

        self._ws_connection.close()
        self._ws_connection = None

    async def _connect_callback(self, future):
        if future.exception() is None:
            self._ws_connection = future.result()
            self._on_connection_success()
            await self._read_messages()
        else:
            self._on_connection_error(future.exception())

    def _read_message(self, msg):
        if msg is None:
            self.service.logerror("received empty websocket message from %s, reconnecting" %
                                  self.service.servicename())
            self.close()
            self.connect()
            return
        try:
            self._on_message(msg)
        except Exception as exception:
            self.service.logerror("failed handling message for %s: %s" % (
                self.service.servicename(), str(exception)
            ))

    async def _read_messages(self):
        while self._ws_connection:
            self._read_message(await self._ws_connection.read_message())

    def _on_message(self, msg):
        """This is called when new message is available from the server.
        :param str msg: server message.
        """

        pass

    def _on_connection_success(self):
        """This is called on successful connection ot the server.
        """

        pass

    def _on_connection_close(self):
        """This is called when server closed the connection.
        """
        self.service.logerror("websocket connection closed for %s" % self.service.servicename())

    def _on_connection_error(self, exception):
        """This is called in case if connection to the server could
        not established.
        """
        self.service.logerror("connection error for %s: %s" % (
            self.service.servicename(), str(exception)
        ))
