# -*- coding: utf-8 -*-
"""
Created on Fri Jul 26 12:36:28 2024

@author: User
"""
#region imports
from AlgorithmImports import *

from universe import CountryEquityIndexUniverseSelectionModel
from alpha import MeanReversionAlphaModel
#endregion


class CountryEquityIndexesMeanReversionAlgorithm(QCAlgorithm):

    _undesired_symbols_from_previous_deployment = []
    _checked_symbols_from_previous_deployment = False
    _previous_expiry_time = None

    def initialize(self):
        self.set_start_date(2023, 3, 1)  # Set Start Date
        self.set_end_date(2024, 3, 1) 
        self.set_cash(1_000_000) 

        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        self.settings.minimum_order_margin_portfolio_percentage = 0

        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
        self.add_universe_selection(CountryEquityIndexUniverseSelectionModel())
        
        self.add_alpha(MeanReversionAlphaModel(
            self.get_parameter("roc_period_months", 6) * 21,
            self.get_parameter("num_positions_per_side", 5)
        ))
        
        self.settings.rebalance_portfolio_on_security_changes = False
        self.settings.rebalance_portfolio_on_insight_changes = False
        self.set_portfolio_construction(EqualWeightingPortfolioConstructionModel(self._rebalance_func))

        self.add_risk_management(NullRiskManagementModel())

        self.set_execution(ImmediateExecutionModel())

        self.set_warm_up(timedelta(31))

    def _rebalance_func(self, time):
        # Rebalance when all of the following are true:
        # - There are new insights or old insights have been cancelled since the last rebalance
        # - The algorithm isn't warming up
        # - There is QuoteBar data in the current slice
        latest_expiry_time = sorted([insight.close_time_utc for insight in self.insights], reverse=True)[0] if self.insights.count else None
        if self._previous_expiry_time != latest_expiry_time and not self.is_warming_up and self.current_slice.quote_bars.count > 0:
            self._previous_expiry_time = latest_expiry_time
            return time
        return None

    def on_data(self, data):
        # Exit positions that aren't backed by existing insights.
        # If you don't want this behavior, delete this method definition.
        if not self.is_warming_up and not self._checked_symbols_from_previous_deployment:
            for security_holding in self.portfolio.values():
                if not security_holding.invested:
                    continue
                symbol = security_holding.symbol
                if not self.insights.has_active_insights(symbol, self.utc_time):
                    self._undesired_symbols_from_previous_deployment.append(symbol)
            self._checked_symbols_from_previous_deployment = True
        
        for symbol in self._undesired_symbols_from_previous_deployment:
            if self.is_market_open(symbol):
                self.liquidate(symbol, tag="Holding from previous deployment that's no longer desired")
                self._undesired_symbols_from_previous_deployment.remove(symbol)

