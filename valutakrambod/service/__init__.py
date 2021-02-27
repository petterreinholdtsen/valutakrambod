# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

from .bitfinex import Bitfinex
from .bitmynt import Bitmynt
from .bitpay import Bitpay
from .bitstamp import Bitstamp
from .bl3p import Bl3p
from .coinbase import Coinbase
from .exchangerates import Exchangerates
from .gemini import Gemini
from .hitbtc import Hitbtc
from .kraken import Kraken
from .miraiex import MiraiEx
from .nbx import Nbx
from .norgesbank import Norgesbank
from .oneforge import OneForge
from .paymium import Paymium

# Services requiring access keys or other configuration
__SERVICES_LIMITED__ = [
    OneForge,
]

# Services working without any configuration
__SERVICES__ = [
    Bitfinex,
    Bitmynt,
    Bitpay,
    Bitstamp,
    Bl3p,
    Coinbase,
    Exchangerates,
    Gemini,
    Hitbtc,
    Kraken,
    MiraiEx,
    Nbx,
    Norgesbank,
    Paymium,
]

__SERVICES_ALL__ = []
__SERVICES_ALL__.extend(__SERVICES__)
__SERVICES_ALL__.extend(__SERVICES_LIMITED__)

def knownServices():
    return __SERVICES__
