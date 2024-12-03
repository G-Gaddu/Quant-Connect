# Import the required packages
from AlgorithmImports import *
from scipy import optimize
from scipy.optimize import Bounds
from factors import *


class FamaFrenchOptimizationAlgorithm(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2014, 12, 3) # Set the start date (say 10 years from today)
        self.set_end_date(2024, 12, 3) # Set the end date 
        self.set_cash(10000000) # Set the strategy cash
        self.settings.automatic_indicator_warm_up = True # Before we start trading using our indicators we need to warm them up
        spy = Symbol.create('SPY', SecurityType.EQUITY, Market.USA) # Define the index that we will be using 
        self.universe_settings.resolution = Resolution.HOUR # Use hourly resolution in trading
        universe_size = self.get_parameter('universe_size', 20) # Define the size of our trading universe, in this case it will be 50 stocks in the S&P 500 
        self._universe = self.add_universe(self.universe.etf(spy, universe_filter_func=lambda constituents: [c.symbol for c in sorted([c for c in constituents if c.weight], key=lambda c: c.weight)[-universe_size:]])) # Define the universe of stocks to be the 50 largest stocks by market cap in the S&P 500
        self._lookback = self.get_parameter('lookback', 60) # Set the lookback period to 60 business days
        # Rebalance the portfolio after 31 days
        self.schedule.on(self.date_rules.month_start(spy), self.time_rules.after_market_open(spy, ), self._rebalance)

    #  Pull the factors that have been defined in the factors script
    def on_securities_changed(self, changes):
        for security in changes.added_securities: 
            security.factors = [MKT(security), SMB(security), HML(security), RMW(security), CMA(security)]

    def _rebalance(self):
        # Obtain the raw factor data for each of the constituents
        factors_df = pd.DataFrame()
        for symbol in self._universe.selected:
            for i, factors in enumerate(self.securities[symbol].factors):
                factors_df.loc[symbol, i] = factors.value
        # Determine the z scores for each of the factors
        factor_zscores = (factors_df - factors_df.mean()) / factors_df.std()
        # Run an optimisation to maximise the trailing returns to determine the optimal factor weights
        trailing_return = self.history(list(self._universe.selected), self._lookback, Resolution.DAILY).close.unstack(0).pct_change(self._lookback-1).iloc[-1]
        num_factors = factors_df.shape[1]
        factor_weights = optimize.minimize(lambda weights: -(np.dot(factor_zscores, weights) * trailing_return).sum(), x0=np.array([1.0/num_factors] * num_factors), method='Nelder-Mead', bounds=Bounds([0] * num_factors, [1] * num_factors), options={'maxiter': 10}).x
        # Determine the portfolio weights
        portfolio_weights = (factor_zscores * factor_weights).sum(axis=1)
        portfolio_weights = portfolio_weights[portfolio_weights > 0]
        self.set_holdings([PortfolioTarget(symbol, weight/portfolio_weights.sum()) for symbol, weight in portfolio_weights.items()], True)