# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from .bitpay import Bitpay
from .bitstamp import Bitstamp
from .coinbase import Coinbase
from .kraken import Kraken
from .paymium import Paymium

__SERVICES__ = [
    Bitpay,
    Bitstamp,
    Coinbase,
    Kraken,
    Paymium,
]

def knownServices():
    return __SERVICES__
