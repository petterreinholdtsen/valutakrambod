# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

__version__ = "0.0.0"
__author__ = "Petter Reinholdtsen <pere@hungry.com>"

"""
http://api.bitcoincharts.com/v1/markets.json
http://api.hitbtc.com/api/1/public/BTC$cur/ticker
http://finance.yahoo.com/d/quotes.csv?e=.csv&f=sl1d1t1&s=$pair=X
http://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.finance.xchange%20where%20pair=%22usdnok%22%20or%20pair=%22eurnok%22&env=store://datatables.org/alltableswithkeys&format=json
https://api.bitcoinsnorway.com:8400/ajax/v1/GetTicker
https://api.bl3p.eu/1/BTCEUR/ticker
https://api.coinbase.com/v2/prices/buy?currency=$cur"
https://api.coinbase.com/v2/prices/sell?currency=$cur
https://api.justcoin.com/api/v1/markets
https://api.kraken.com/0/public/Ticker?pair=$cur
https://bitpay.com/rates/$cur
https://data.mtgox.com/api/2/BTC$currency/money/ticker_fast
https://forex.1forge.com/1.0.1/quotes?pairs=USDEUR,EURNOK,USDNOK&api_key=jgO1GKujpulMciW9VdsiD2f13MtKD9ri
https://justcoin.com/api/v1/markets
https://paymium.com/api/v1/data/eur/ticker
https://www.bitstamp.net/api/v2/ticker/btc$cur/
http://www.norges-bank.no/RSS/Amerikanske-dollar-USD---dagens-valutakurs-fra-Norges-Bank/
http://www.norges-bank.no/RSS/Euro-EUR---dagens-valutakurs-fra-Norges-Bank/

"""

import kaupang.service

from tornado import ioloop

def bcc_transaction_stream(callback):
    """
Telnet interface
There is an experimental telnet streaming interface on TCP port 27007 at
api.bitcoincharts.com.

This service is strictly for personal use. Do not assume this data to be 100%
accurate or write trading bots that rely on it.
"""

def BTCrates():
    collectors = []
    for e in kaupang.service.knownServices():
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
