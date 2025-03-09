# Import the required packages
 
from AlgorithmImports import *
from futures_contracts import contracts
from weights import GetWeights

class CarryTrendAlpha(AlphaModel):
    # Define the initial parameters we will be working with
    futures = []
    business_days = 256
    trend_forecast_scalars = {2: 12.1, 4: 8.53, 8: 5.95, 16: 4.1, 32: 2.79, 64: 1.91} 
    carry_forecast_scalar = 30 
    fdm_by_count = {1: 1.0, 2: 1.02, 3: 1.03, 4: 1.23, 5: 1.25, 6: 1.27, 7: 1.29, 8: 1.32, 9: 1.34}

    def __init__(self, algorithm, emac_filters, abs_forecast_limit, sigma_range, risk_tol, blend_years):
        # Initialise the class first for the EMAC parameters then the carry ones
        self.algorithm = algorithm
        self.emac_range = [2**x for x in range(4, emac_filters+1)]
        self.fast_ema_range = self.emac_range
        self.slow_ema_range = [fast_range * 4 for fast_range in self.emac_range] 
        self.all_ema_range = sorted(list(set(self.fast_ema_range + self.slow_ema_range)))
        
        self.carry_range = [5, 20, 60, 120]
        
        self.annualisation_factor = self.business_days ** 0.5
        self.abs_forecast_limit = abs_forecast_limit
        self.blend_years = blend_years
        self.contracts = contracts
        self.day = -1
        self.lookback_period = timedelta(sigma_range*(7/5) + blend_years*365)
        # Instrument Diversification Multiplier
        self.idm = 1.5    
        self.sigma_range = sigma_range
        self.risk_tol = risk_tol                                          
        

    # Define a function that updates the signal
    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        if data.quote_bars.count:
            for future in self.futures:
                future.latest_mapped = future.mapped

        # Rebalance on a daily basis 
        if self.day == data.time.day or data.quote_bars.count == 0:
            return []

        # Update the annualised carry data
        for future in self.futures:
            # Obtain the near and far contracts
            contracts = self.get_near_and_further_contracts(algorithm.securities, future.mapped)
            if contracts is None:
                continue
            near_contract, further_contract = contracts[0], contracts[1]
            
            # The near and far contracts are then saved for future reference
            future.near_contract = near_contract
            future.further_contract = further_contract

            # Determine if the daily consolidator has provided a bar for any of the contracts
            if not hasattr(near_contract, "raw_history") or not hasattr(further_contract, "raw_history") or near_contract.raw_history.empty or further_contract.raw_history.empty:
                continue
            # Then update the raw carry data on an annualised basis
            raw_carry_data = near_contract.raw_history.iloc[0] - further_contract.raw_history.iloc[0]
            month_diff = round((further_contract.expiry - near_contract.expiry).days / 30)
            year_diff = abs(month_diff) / 12
            annualised_raw_carry = raw_carry_data / year_diff
            future.annualised_raw_carry_history.loc[near_contract.raw_history.index[0]] = annualised_raw_carry

        # If we are in the warm up period and more than 10 days from the start date then do nothing
        # This is done so that we have insights at the end of the warm up period 
        if algorithm.start_date - algorithm.time > timedelta(10):
            self.day = data.time.day
            return []
        
        # Estimate the standard deviation of % daily returns for each future
        std_pct_by_contract = {}
        for future in self.futures:
            std_pcts = self.estimate_std_of_rets(future.raw_history, future.adjusted_history)
            # First determine if there is sufficient data
            if std_pcts is None:
                continue
            std_pct_by_contract[future] = std_pcts

        # Then generate the insights that will drive our strategy
        insights = []
        weight_by_ticker = GetWeights({future.symbol: self.contracts[future.symbol].classification for future in std_pct_by_contract.keys()})
        for ticker, instrument_weight in weight_by_ticker.items():
            future = algorithm.securities[ticker]
            target_contract = [future.near_contract, future.further_contract][self.contracts[future.symbol].contract_offset]
            std_pct = std_pct_by_contract[future]
            daily_risk_prices = std_pct / (self.annualisation_factor) * target_contract.price 

            # Determine the target position
            position = (algorithm.portfolio.total_portfolio_value * self.idm * instrument_weight * self.risk_tol)/(future.symbol_properties.contract_multiplier * daily_risk_prices * (self.annualisation_factor))

            # Determine the EMAC forecast
            emac_forecasts = self.calculate_emac_forecasts(future.ewmac_by_range, daily_risk_prices)
            if not emac_forecasts:
                continue
            emac_combined_forecasts = sum(emac_forecasts) / len(emac_forecasts) 

            # Determine the carry forecast
            raw_carry_forecasts = self.calculate_carry_forecasts(future.annualised_raw_carry_history, daily_risk_prices)
            if not raw_carry_forecasts:
                continue
            carry_combined_forecasts = sum(raw_carry_forecasts) / len(raw_carry_forecasts) 
            
            # Finally, we create a forecast that takes 65% of the EMAC signal and 35% of the carry signal 
            raw_combined_forecast = 0.65 * emac_combined_forecasts + 0.35 * carry_combined_forecasts
            scaled_combined_forecast = raw_combined_forecast * self.fdm_by_count[len(emac_forecasts) + len(raw_carry_forecasts)] 
            capped_combined_forecast = max(min(scaled_combined_forecast, self.abs_forecast_limit), -self.abs_forecast_limit)

            if capped_combined_forecast * position == 0:
                continue
            target_contract.forecast = capped_combined_forecast
            target_contract.position = position
            
            local_time = Extensions.convert_to(algorithm.time, algorithm.time_zone, future.exchange.time_zone)
            expiry = future.exchange.hours.get_next_market_open(local_time, False) - timedelta(seconds=1)
            insights.append(Insight.price(target_contract.symbol, expiry, InsightDirection.UP if capped_combined_forecast * position > 0 else InsightDirection.DOWN))
        
        if insights:
            self.day = data.time.day

        return insights

    # Define a function that will account for any changes in our investment uniders
    def on_securities_changed(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        for security in changes.added_securities:
            symbol = security.symbol

            # First reate a consolidator to update the history of any new futures added
            security.consolidator = TradeBarConsolidator(timedelta(1))
            security.consolidator.data_consolidated += self.consolidation_handler
            algorithm.subscription_manager.add_consolidator(symbol, security.consolidator)

            # Then update the raw and adjusted history
            security.raw_history = pd.Series()

            if symbol.is_canonical():
                security.adjusted_history = pd.Series()
                security.annualised_raw_carry_history = pd.Series()

                # Then generate the indicators for the contract
                ema_by_range = {span: algorithm.EMA(symbol, span, Resolution.DAILY) for span in self.all_ema_range}
                security.ewmac_by_range = {}
                for i, fast_range in enumerate(self.emac_range):
                    security.ewmac_by_range[fast_range] = IndicatorExtensions.minus(ema_by_range[fast_range], ema_by_range[self.slow_ema_range[i]])

                security.automatic_indicators = ema_by_range.values()

                self.futures.append(security)

        for security in changes.removed_securities:
            # Finally remove the consolidator and the indicators
            algorithm.subscription_manager.remove_consolidator(security.symbol, security.consolidator)
            if security.symbol.is_canonical():
                for indicator in security.automatic_indicators:
                    algorithm.deregister_indicator(indicator)    
    
    # Define a function to determine the EMAC forecast for each future
    def calculate_emac_forecasts(self, ewmac_by_range, daily_risk_prices):
        forecasts = []
        for span in self.emac_range:
            # Obtain the risk adjusted EWMAC, then scale it and cap. 
            risk_adjusted_ewmac = ewmac_by_range[span].current.value / daily_risk_prices
            scaled_forecast_ewmac = risk_adjusted_ewmac * self.trend_forecast_scalars[span]
            capped_forecast_ewmac = max(min(scaled_forecast_ewmac, self.abs_forecast_limit), -self.abs_forecast_limit)
            forecasts.append(capped_forecast_ewmac)
        return forecasts    
    
    # Define a function to determine the carry forecast for each future
    def calculate_carry_forecasts(self, annualised_raw_carry, daily_risk_prices):
        carry_forecast = annualised_raw_carry / daily_risk_prices

        forecasts = []
        for span in self.carry_range:
            # First smooth out the carry forecast
            smooth_carry_forecast = carry_forecast.ewm(span=span, min_periods=span).mean().dropna()
            if smooth_carry_forecast.empty:
                continue
            smooth_carry_forecast = smooth_carry_forecast.iloc[-1]
            # Then scale the signal
            scaled_carry_forecast = smooth_carry_forecast * self.carry_forecast_scalar
            # Then cap it
            capped_carry_forecast = max(min(scaled_carry_forecast, self.abs_forecast_limit), -self.abs_forecast_limit)
            forecasts.append(capped_carry_forecast)

        return forecasts    
    
    # Define a function to obtain and align the historical data for each contract
    def get_near_and_further_contracts(self, securities, mapped_symbol):
       
        futures_sorted_by_expiry = sorted(
            [kvp.Value for kvp in securities 
            if not kvp.key.is_canonical() and kvp.key.canonical == mapped_symbol.canonical and kvp.Value.Expiry >= securities[mapped_symbol].Expiry
            ], 
        key=lambda contract: contract.expiry)
        if len(futures_sorted_by_expiry) < 2:
            return None
        near_contract = futures_sorted_by_expiry[0]
        further_contract = futures_sorted_by_expiry[1]
        return near_contract, further_contract    

    # Then create a function to estimate the standard deviation of the percentage returns 
    def estimate_std_of_rets(self, raw_history, adjusted_history):
        # First align the history of the raw and adjusted prices
        raw_history_aligned, adjusted_history_aligned = self.align_history(raw_history, adjusted_history)

        # Then determine the exponentially weighted standard deviation of the returns
        returns = adjusted_history_aligned.diff().dropna() / raw_history_aligned.shift(1).dropna() 
        rolling_ewmstd_pct_returns = returns.ewm(span=self.sigma_range, min_periods=self.sigma_range).std().dropna()
        # If there is no data then do nothing
        if rolling_ewmstd_pct_returns.empty: 
            return None
        # Then obtain the annualised estimate of the standard deviation
        annualised_rolling_ewmstd_pct_returns = rolling_ewmstd_pct_returns * (self.annualisation_factor)
        # Finally obtain a blended estimate
        blended_estimate = 0.3*annualised_rolling_ewmstd_pct_returns.mean() + 0.7*annualised_rolling_ewmstd_pct_returns.iloc[-1]
        return blended_estimate    
    
    # Create a function to align the history of two databases
    def align_history(self, a, b):
        idx = sorted(list(set(a.index).intersection(set(b.index)))) 
        return a.loc[idx], b.loc[idx]


    def consolidation_handler(self, sender: object, consolidated_bar: TradeBar) -> None:
        security = self.algorithm.securities[consolidated_bar.symbol]
        end_date = consolidated_bar.end_time.date()
        if security.symbol.is_canonical():
            # Update the adjusted history
            security.adjusted_history.loc[end_date] = consolidated_bar.close
            security.adjusted_history = security.adjusted_history[security.adjusted_history.index >= end_date - self.lookback_period]
        else:
            # Otherwise update the raw history
            continuous_contract = self.algorithm.securities[security.symbol.canonical]
            if hasattr(continuous_contract, "latest_mapped") and consolidated_bar.symbol == continuous_contract.latest_mapped:
                continuous_contract.raw_history.loc[end_date] = consolidated_bar.close
                continuous_contract.raw_history = continuous_contract.raw_history[continuous_contract.raw_history.index >= end_date - self.lookback_period]
            
            # Update the raw carry history
            security.raw_history.loc[end_date] = consolidated_bar.close
            security.raw_history = security.raw_history.iloc[-1:]



