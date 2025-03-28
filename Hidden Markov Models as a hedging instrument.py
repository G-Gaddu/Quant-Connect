# First import the required packages
from AlgorithmImports import *
from hmmlearn.hmm import GMMHMM
from scipy.optimize import minimize
# The set the seed
np.random.seed(42)

class DrawdownRegimeGoldHedgeAlgorithm(QCAlgorithm):
    # Initialise the class
    def initialize(self) -> None:
        # Set the start and end date, cash allocated and brokerage model
        self.set_start_date(2018, 3, 28)
        self.set_end_date(2025, 3, 28)
        self.set_cash(10000000)
        self.set_security_initializer(BrokerageModelSecurityInitializer(self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices)))

        # Then define the historical and drawdown lookback periods
        self.drawdown_lookback_window = self.get_parameter("drawdown_lookback_window", 20)
        self.history_lookback_window = self.get_parameter("history_lookback_window", 50)
        
        # Set the S&P500 as the benchmarket and for hidden Markov model fitting
        self.sp500 = self.add_equity("SPY", Resolution.MINUTE).symbol
        # Set gold as the hedge asset
        self.gold = self.add_equity("GLD", Resolution.MINUTE).symbol
        self.set_benchmark(self.sp500)

        # Rebalance the portfolio at the start of each week, 1 minute after the market opens
        self.schedule.on(self.date_rules.week_start(self.sp500), self.time_rules.after_market_open(self.sp500, 1), self.rebalance_portfolio)
    
    def rebalance_portfolio(self) -> None:
        # First obtain the drawdown to be used as an input, we rebalance weekly so resample the data to obtain the weekly drawdown
        drawdown_history = self.history(self.sp500, self.history_lookback_window*5, Resolution.DAILY).unstack(0).close.resample('W').last()
        drawdown = drawdown_history.rolling(self.drawdown_lookback_window).apply(lambda x: (x.iloc[-1] - x.max()) / x.max()).dropna()

        try:
            # First intialise the Hidden Markov Model, then fit by the drawdown data
            features = np.concatenate([drawdown[[self.sp500]].iloc[1:].values, drawdown[[self.sp500]].diff().iloc[1:].values], axis=1)
            HMM_model = GMMHMM(n_components=2, n_mix=3, covariance_type='tied', n_iter=100, random_state=42).fit(features)
            # Then determine the hidden market regime
            regime_pred_prob = HMM_model.predict_proba(features)
            current_regime_pred_prob = regime_pred_prob[-1]
            current_regime = 0 if current_regime_pred_prob[0] > current_regime_pred_prob[1] else 1

            # Then determine the regime number, a higher coeffcient means a larger drawdown
            high_regime = 1 if HMM_model.means_[0][1][0] < HMM_model.means_[1][1][0] else 0
            # Then determine the transitional probaility of the next regime being a high volatility regime
            # The transitional probability is given by the probability of the existing regime being 1/0 which is
            # multiplied by the posterior probability of each scenario
    
            next_pred_prob_zero = current_regime_pred_prob @ HMM_model.transmat_[:, 0]
            next_prob_pred_high = round(next_pred_prob_zero if high_regime == 0 else 1 - next_pred_prob_zero, 2)

            # If it is easier to have a larger drawdown during the existing regime then buy more gold and less S&P500
            # The weighings will be assigned by the posterior probabilities.
            self.set_holdings([PortfolioTarget(self.gold, next_prob_pred_high), PortfolioTarget(self.sp500, 1 - next_prob_pred_high)])

        except:
            pass