# Import the necessary packages
from AlgorithmImports import *
from scipy.optimize import minimize

class RISKPARITYINETFS(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 12, 4) # Define the start point
        self.set_end_date(2024, 12, 4) # Set the end date
        self.set_cash(1000000) # Set the cash allocated to the strategy
        # Define the ETFs that we are interested in (S&P500, Japanese and European Equities, Options, Bonds, Commodities, Blockchain and Bitcoin)
        self.symbols = [self.add_equity(ticker, data_normalization_mode=DataNormalizationMode.RAW).symbol for ticker in ["TQQQ", "SVXY", "EZJ", "UPV", "EDZ", "VXX", "UJB", "DIG", "UGL", "BITS"]]
        # Define when we start to form a portfolio and when we rebalance them
        self.schedule.on(self.date_rules.month_start(), self.time_rules.at(20, 0), self.rebalance)

    def rebalance(self):
        # Get the returns for each ETF for the last year
        ret = self.history(self.symbols, 252, Resolution.DAILY).close.unstack(0).pct_change().dropna()
        # Get the weights through optimising the objective function for risk parity
        x0 = [1/ret.shape[1]] * ret.shape[1]
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
        bounds = [(0, 1)] * ret.shape[1]
        opt = minimize(lambda w: 0.5 * (w.T @ ret.cov() @ w) - x0 @ w, x0=x0, constraints=constraints, bounds=bounds, tol=1e-8, method="SLSQP")
        self.set_holdings([PortfolioTarget(symbol, weight) for symbol, weight in zip(ret.columns, opt.x)])