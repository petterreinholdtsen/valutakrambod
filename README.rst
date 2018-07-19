Valutakrambod
=============

Valutakrambod is a constructed Norwegian word for for currency
market-place.

This project is a pluggable (virtual) currency exchange API client
library providing a uniform API to several currency exchanges.

To test the default set of services in a simple curses application
directly from the git repository, try this::

  PYTHONPATH=`pwd` python3 bin/btc-rates-curses -c

A similar library written in Java named `XChange`_ can be used for
inspiration.

.. _XChange: https://github.com/knowm/XChange


Some useful links:

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


Docker

  # Build
  docker build -t valutakrambod .
  # Run tests
  docker run --rm -it valutakrambod python3 setup.py test
