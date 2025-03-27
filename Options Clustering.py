# First import the required packages
from AlgorithmImports import *
from sklearn.cluster import KMeans

class ImpliedVolatilityClustering(QCAlgorithm):

    def initialize(self):
        # First set the start date, end data and cash assigned to the strategy
        self.set_start_date(2015, 3, 25)
        self.set_end_date(2025, 3, 25)
        self.set_cash(10000000)
        # Define the brokerage model, the underlying index and the index volatility
        self.set_security_initializer(BrokerageModelSecurityInitializer(self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices)))
        self._underlyingindex = self.add_index('SPX')
        self._underlyingindex.std = self.std(self._underlyingindex.symbol, 22, Resolution.DAILY)
        # Then define the options we were interested in, filter by expiry and strike, determine implied volaility and strike availability
        self._derivative = self.add_index_option(self._underlyingindex.symbol)
        self._derivative.set_filter(lambda universe: universe.include_weeklys().expiration(30, 100).strikes(-1, 1))  
        self._derivative.impliedvol_rank = ImpliedVolRank()
        self._derivative.strike_avail = StrikeAvail()
        self._derivative.contract = None
        # Then schedule rebalancing each day, 1 minute after the market opens and define a warm up period of 1 year
        self.schedule.on(self.date_rules.every_day(self._underlyingindex.symbol), self.time_rules.after_market_open(self._underlyingindex.symbol, 1), self._rebalanceportfolio)
        self.set_warm_up(timedelta(365))

    def _rebalanceportfolio(self):
        # First update the strike availability indicator
        chain = self.option_chain(self._underlyingindex.symbol, flatten=True).data_frame
        if chain.empty:
            return
        if self._derivative.strike_avail.update(self.time, chain):
            self.plot('Strike Availability', 'Label', self._derivative.strike_avail.label)
            self.plot('Strike Availability', 'Value', self._derivative.strike_avail.value)
        # Then update the implied volatility rank indicator
        universe_chain = self.current_slice.option_chains.get(self._derivative.symbol)
        if not universe_chain or not self._derivative.impliedvol_rank.update(universe_chain) or self.is_warming_up:
            return
        self.plot('Implied Volatility Rank', 'Value', self._derivative.impliedvol_rank.value)
        self.plot('Implied Volatility Rank', 'Label', self._derivative.impliedvol_rank.label)
        # If the portfolio is invested then liquidate under the following conditions
        if self.portfolio.invested:
            # If the implied vol and availability rank are both 2
            if self._derivative.impliedvol_rank.label == 2 and self._derivative.strike_avail.label == 2:
                self.liquidate(tag='IV rank and strike availability is high!')
            # If the contract is approaching at the money
            elif self._underlyingindex.price <= self._derivative.contract.id.strike_price:
                self.liquidate(tag='ATM')
            # If the contract will expire in less than 5 days 
            elif self._derivative.contract.id.date - self.time < timedelta(7):
                self.liquidate(tag=f'Expires within 7 days')
        # If the Implied Vol has a low rank then we expect low volatility in the future
        # We should therefore sell at the money put contracts to collect the premium. As the S&P500 has an upward drift, the contracts
        # should expire out of the money
        elif self._derivative.impliedvol_rank.label < 2 and self._derivative.strike_avail.label < 2:
            chain = chain[(chain.expiry == chain.expiry[chain.expiry - self.time >= timedelta(30)].min()) & (chain.right == OptionRight.PUT) & (chain.strike <= self._underlyingindex.price)].sort_values('strike')
            self._derivative.contract = chain.index[-min(int(3*self._underlyingindex.std.current.value/5), len(chain))]
            self.add_option_contract(self._derivative.contract)
            self.set_holdings(self._derivative.contract, -0.25)

class ImpliedVolRank:
    # Initialise the class to determine the rank of the implied volatility
    def __init__(self, lookback_period=252, min_expiry_period=30):
        self._max_impliedvol = Maximum(lookback_period)
        self._min_impliedvol = Minimum(lookback_period)
        self._min_expiry_period = timedelta(min_expiry_period)
        self._history = RollingWindow[float](lookback_period)

    def update(self, chain):
        # We select the contracts that we will use in the aggregation process
        # First select contracts that expire after 1 month from the current date
        expire_1_month= [x.id.date for x in chain if x.id.date >= chain.end_time + self._min_expiry_period]
        if not expire_1_month:
            return
        expiry_dates = min([x.id.date for x in chain if x.id.date >= chain.end_time + self._min_expiry_period])
        valid_contracts = [x for x in chain if x.id.date == expiry_dates]
        #  Then look at At The Money Contracts
        abs_delta_by_ticker = {x.symbol: abs(x.underlying_last_price - x.id.strike_price) for x in valid_contracts}
        abs_delta = min(abs_delta_by_ticker.values())
        atm_contracts = [x for x in valid_contracts if abs_delta_by_ticker[x.symbol] == abs_delta]
        # Then aggregate the implied volatility of the selected contracts
        aggregate_impliedvol = float(np.median([x.implied_volatility for x in atm_contracts]))
        self._history.add(aggregate_impliedvol)
        # Calculate the IV Rank and determine if it's high, medium, or low.
        self._min_impliedvol.update(chain.end_time, aggregate_impliedvol)
        self.is_ready = self._max_impliedvol.update(chain.end_time, aggregate_impliedvol)
        if self.is_ready:
            self.value = float((aggregate_impliedvol - self._min_impliedvol.current.value) / (self._max_impliedvol.current.value - self._min_impliedvol.current.value))
            # Apply clustering to break into 3 groups: low, medium and high
            kmeans = KMeans(n_clusters=3, random_state=0).fit(np.array(list(self._history)[::-1]).reshape(-1, 1))
            # Now modify the labels so that 0=Low, 1=Medium, 2=High.
            label_key = {original: sorted_ for sorted_, original in enumerate(np.argsort(kmeans.cluster_centers_.ravel()))}
            labels = [label_key[label] for label in kmeans.labels_]
            # Save the labels
            self.label = labels[-1] 
        return self.is_ready

class StrikeAvail:
    # Initialise the class to deterimine the rank of the strike availability
    def __init__(self, lookback_window=252, period=10):
        self._roc = RateOfChange(period)
        self._roc.window.size = lookback_window
        self._roc.window.reset()
    
    def update(self, x, option_chain):
        # Update the rate of change indicator and ensure readiness
        self._roc.update(x, len(option_chain.strike.unique()) / option_chain.underlyinglastprice.iloc[0])
        self.is_ready = self._roc.window.is_ready
        # Apply K means clustering with the labels so that 0 = low, 1 = medium and 2 = high
        if self.is_ready:
            self.value = self._roc.current.value
            kmeans = KMeans(n_clusters=3, random_state=0).fit(np.array([x.value for x in self._roc.window][::-1]).reshape(-1, 1))            
            label_key = {original: sorted_ for sorted_, original in enumerate(np.argsort(kmeans.cluster_centers_.ravel()))}
            labels = [label_key[label] for label in kmeans.labels_]
            # Finally save the labels
            self.label = labels[-1]
        return self.is_ready

