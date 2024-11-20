# -*- coding: utf-8 -*-
"""
Created on Wed Nov 20 16:06:33 2024

@author: User
"""
from AlgorithmImports import *

class PlatinumFuturesContangoStrategy(QCAlgorithm):
    def initialize(self):
        # Define the period of our strategy and the initial investment
        self.set_start_date(2019, 11, 20)
        self.set_end_date(2024,11, 20)
        self.set_cash(1000000)

        # Subscribe and set our expiry filter for the futures chain
        self.future_p_l_a_t = self.add_future(
            Futures.Metals.PLATINUM, 
            resolution = Resolution.MINUTE,
            data_normalization_mode = DataNormalizationMode.BACKWARDS_RATIO,
            data_mapping_mode = DataMappingMode.OPEN_INTEREST,
            contract_depth_offset = 0
        )
        # Set the expiry date on the contracts to be between 0 and 60 days, we don't want to hold them for too long
        self.future_p_l_a_t.set_filter(0, 90)

        # Apply the 20 day SMA as the basis mean reversion predictor
        self.roc = self.ROC(self.future_p_l_a_t.symbol, 1, Resolution.DAILY)
        self.sma = IndicatorExtensions.of(SimpleMovingAverage(20), self.roc)
        self.set_warm_up(21, Resolution.DAILY)

        # Take the iShares 7-10 year bond ETF as the benchmark
        BOND_ETF = self.add_equity("IEF").symbol
        self.set_benchmark(BOND_ETF)

    def on_data(self, slice):
        if not self.portfolio.invested and not self.is_warming_up:
            # Trading only occurs when the last day return is less than the average return
            if not self.roc.is_ready or not self.sma.is_ready or self.sma.current.value < self.roc.current.value:
                return

            spreads = {}

            for chain in slice.future_chains:
                contracts = list(chain.value)

                # If the number of contracts is less than 2 then we can't compare the spot prices
                if len(contracts) < 2: continue

                # Sort the contracts by expiry dates
                sorted_contracts = sorted(contracts, key=lambda x: x.expiry)
                # Compare the spot prices of the contracts
                for i, contract in enumerate(sorted_contracts):
                    if i == 0: continue

                    # Compare the ask prices of contracts that are close to each other in terms of expiry dates
                    for j in range(i):
                        near_contract = sorted_contracts[j]

                        # Determine the spread and total cost
                        spread = contract.bid_price - near_contract.ask_price
                        total_cost = contract.bid_price + near_contract.ask_price + 2
                        spreads[(contract.symbol, near_contract.symbol)] = (spread, total_cost)

            # Trade the pair with the lowest spread to maximise the contango
            if spreads:
                min_spread_pair = sorted(spreads.items(), key=lambda x: x[1][0])[0]
                far_contract, near_contract = min_spread_pair[0]

                # Subscribe the contracts to avoide removing them from the universe in the future
                self.add_future_contract(far_contract, Resolution.MINUTE)
                self.add_future_contract(near_contract, Resolution.MINUTE)

                num_of_contract = max((self.portfolio.total_portfolio_value / min_spread_pair[1][1]) // self.future_p_l_a_t.symbol_properties.contract_multiplier, 1)
                self.market_order(far_contract, num_of_contract)
                self.market_order(near_contract, -num_of_contract)