# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from .bitmynt import Bitmynt
from .bitpay import Bitpay
from .bitstamp import Bitstamp
from .bl3p import Bl3p
from .coinbase import Coinbase
from .exchangerates import Exchangerates
from .hitbtc import Hitbtc
from .kraken import Kraken
from .miraiex import MiraiEx
from .oneforge import OneForge
from .paymium import Paymium

# Services requiring access keys or other configuration
__SERVICES_LIMITED__ = [
    OneForge,
]

# Services working without any configuration
__SERVICES__ = [
    Bitmynt,
    Bitpay,
    Bitstamp,
    Bl3p,
    Coinbase,
    Exchangerates,
    Hitbtc,
    Kraken,
    MiraiEx,
    Paymium,
]

__SERVICES_ALL__ = []
__SERVICES_ALL__.extend(__SERVICES__)
__SERVICES_ALL__.extend(__SERVICES_LIMITED__)

def knownServices():
    return __SERVICES__
