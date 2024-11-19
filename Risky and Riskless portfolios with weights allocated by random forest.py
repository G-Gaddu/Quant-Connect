# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 23:20:26 2024

@author: User
"""
# Import the necesssary packages

from AlgorithmImports import *
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor



class RiskyandRiskless6040portfolio(QCAlgorithm):

    def initialize(self):
        # Define the time horizon, we will use the last 10 years from today
        self.set_start_date(2014,11,19)
        self.set_end_date(2024,11,19)
        # Set the cash committed to the strategy
        self.set_cash(10000000)  
        self.settings.daily_precise_end_time = False
        # Define the assets used in the strategy, first is Bitcoin
        self._bitcoin = self.add_crypto("BTCUSD", market=Market.BITFINEX, leverage=5).symbol
        # Use the SPDR Gold Trust as a proxy for gold and the Vanguard total bond index ETF as a proxy for bonds
        self._equities = [self.add_equity(ticker).symbol for ticker in ['GLD', 'BND', 'SPY']]
        # Define the three factors that we will be using
        self._factors = [self.add_data(Fred, ticker, Resolution.DAILY).symbol for ticker in ['DFF','T10Y3M', 'VIXCLS']]
        # Then the model
        self._model = RandomForestRegressor(n_estimators = 10, min_samples_split=2,max_depth=12, random_state=1)
        self._scaler = StandardScaler()
        self.schedule.on(self.date_rules.month_start(self._equities[0]), self.time_rules.after_market_open(self._equities[0], 1), self._rebalance)
        # Define the lookback period and the maximum allocation to bitcoin in the portfolio
        self._lookback_years = self.get_parameter('lookback_years', 5)
        self._max_bitcoin_weight = self.get_parameter('max_bitcoin_weight', 0.25)
    
    def _rebalance(self):
        # Obtain the factor data over the lookback period
        factors = self.history(self._factors, timedelta(self._lookback_years*365), Resolution.DAILY)['value'].unstack(0).dropna()
        # Get the returns for each asset over the lookback period
        label = self.history(self._equities + [self._bitcoin], timedelta(self._lookback_years*365), Resolution.DAILY, data_normalization_mode=DataNormalizationMode.TOTAL_RETURN)['close'].unstack(0).dropna().pct_change(21).shift(-21).dropna()
        # Create a dataframe to store the predictions
        prediction_by_symbol = pd.Series()
        # For each asset make predictions on the returns of them using the factors as the features
        for symbol in self._equities + [self._bitcoin]:
            asset_labels = label[symbol].dropna()
            idx = factors.index.intersection(asset_labels.index)
            self._model.fit(self._scaler.fit_transform(factors.loc[idx]), asset_labels.loc[idx])
            prediction = self._model.predict(self._scaler.transform([factors.iloc[-1]]))[0]
            if prediction > 0:
                prediction_by_symbol.loc[symbol] = prediction
        # Allocate weights to each asset based on the prediction and form the portfolios
        weight_by_symbol = 1.5 * prediction_by_symbol / prediction_by_symbol.sum()
        if self._bitcoin in weight_by_symbol and weight_by_symbol.loc[self._bitcoin] > self._max_bitcoin_weight:
            weight_by_symbol.loc[self._bitcoin] = self._max_bitcoin_weight
            if len(weight_by_symbol) > 1:
                equities = [symbol for symbol in self._equities if symbol in weight_by_symbol]
                weight_by_symbol.loc[equities] = 1.5 * weight_by_symbol.loc[equities] / weight_by_symbol.loc[equities].sum()
        self.set_holdings([PortfolioTarget(symbol, weight) for symbol, weight in weight_by_symbol.items()], True)