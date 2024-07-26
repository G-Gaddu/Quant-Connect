# -*- coding: utf-8 -*-
"""
Created on Fri Jul 26 12:35:59 2024

@author: User
"""
#region imports
from AlgorithmImports import *
#endregion


class MeanReversionAlphaModel(AlphaModel):

    _securities = []
    _month = -1

    def __init__(self, roc_period, num_positions_per_side):
        self._roc_period = roc_period
        self._num_positions_per_side = num_positions_per_side

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        # Reset indicators when corporate actions occur
        for symbol in set(data.splits.keys() + data.dividends.keys()):
            security = algorithm.securities[symbol]
            if security in self._securities:
                algorithm.unregister_indicator(security.indicator)
                self._initialize_indicator(algorithm, security)
        
        # Only emit insights when there is quote data, not when a corporate action occurs (at midnight)
        if data.quote_bars.count == 0:
            return []

        # Only emit insights once per month
        if self._month == algorithm.time.month:
            return []
        
        # Check if enough indicators are ready
        ready_securities = [security for security in self._securities if security.indicator.is_ready and security.symbol in data.quote_bars]
        if len(ready_securities) < 2 * self._num_positions_per_side:
            return []

        self._month = algorithm.time.month

        # Short securities that have the highest trailing ROC
        sorted_by_roc = sorted(ready_securities, key=lambda security: security.indicator.current.value)
        insights = [Insight.price(security.symbol, Expiry.END_OF_MONTH, InsightDirection.DOWN) for security in sorted_by_roc[-self._num_positions_per_side:]]
        # Long securities that have the lowest trailing ROC
        insights += [Insight.price(security.symbol, Expiry.END_OF_MONTH, InsightDirection.UP) for security in sorted_by_roc[:self._num_positions_per_side]]
        return insights

    def _initialize_indicator(self, algorithm, security):
        security.indicator = algorithm.ROC(security.symbol, self._roc_period, Resolution.DAILY)
        algorithm.warm_up_indicator(security.symbol, security.indicator)

    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        for security in changes.added_securities:
            self._initialize_indicator(algorithm, security)
            self._securities.append(security)

        for security in changes.removed_securities:
            if security in self._securities:
                algorithm.unregister_indicator(security.indicator)
                self._securities.remove(security)

