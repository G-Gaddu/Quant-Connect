# -*- coding: utf-8 -*-
"""
Created on Fri Jul 26 12:35:04 2024

@author: User
"""
#region imports
from AlgorithmImports import *
#endregion


class CountryEquityIndexUniverseSelectionModel(ManualUniverseSelectionModel):
    def __init__(self):
        tickers = [
            "EWJ",  # iShares MSCI Japan Index ETF
            "EFNL", # iShares MSCI Finland Capped Investable Market Index ETF
            "EWW",  # iShares MSCI Mexico Inv. Mt. Idx
            "ERUS", # iShares MSCI Russia ETF
            "IVV",  # iShares S&P 500 Index
            "AUD",  # Australia Bond Index Fund
            "EWQ",  # iShares MSCI France Index ETF
            "EWH",  # iShares MSCI Hong Kong Index ETF
            "EWI",  # iShares MSCI Italy Index ETF
            "EWY",  # iShares MSCI South Korea Index ETF
            "EWP",  # iShares MSCI Spain Index ETF
            "EWD",  # iShares MSCI Sweden Index ETF
            "EWL",  # iShares MSCI Switzerland Index ETF
            "EWC",  # iShares MSCI Canada Index ETF
            "EWZ",  # iShares MSCI Brazil Index ETF
            "EWO",  # iShares MSCI Austria Investable Mkt Index ETF
            "EWK",  # iShares MSCI Belgium Investable Market Index ETF
            "BRAQ", # Global X Brazil Consumer ETF
            "ECH"   # iShares MSCI Chile Investable Market Index ETF
        ]
        symbols = [Symbol.create(ticker, SecurityType.EQUITY, Market.USA) for ticker in tickers]
        super().__init__(symbols)
