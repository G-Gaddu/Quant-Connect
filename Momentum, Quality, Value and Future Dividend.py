#region imports
from AlgorithmImports import *
#endregion

class BasicTemplateAlgorithm(QCAlgorithm):
    
    def __init__(self):
        # Set the rebalancing period to quarterly
        self._reb = 3
        # Determine the number of stocks to pass through the CoarseSelection process
        self._num_coarse = 300
        # Determine the number of stocks to long/short
        self._num_fine = 30
        self._symbols = None

    def initialize(self):
        self.set_cash(10000000) # Determine initial investment
        self.set_start_date(2014,9,1) # Determine start period
        self.set_end_date(2024,9,1) # Determine end period
        
        self.set_security_initializer(BrokerageModelSecurityInitializer(self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices)))
        self._spy = self.add_equity("SPY", Resolution.DAILY).symbol
        
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._coarse_selection_function,self._fine_selection_function)
        
        # Schedule the rebalance function to rebalance the portfolio at the end of each quarter
        self.schedule.on(self.date_rules.month_start(self._spy), self.time_rules.after_market_open(self._spy,5), self._rebalance)
    
    def _coarse_selection_function(self, coarse):
        # If the rebalance flag is not 3 then skip to save time
        if self._reb != 3:
            return self._long + self._short
            
        # Make the universe selection every quarter
        # Drop stocks that have no fundamental data or have too low prices
        selected = [x for x in coarse if (x.has_fundamental_data) and (float(x.price) > 5)]
        # Sort the stocks by dollar volume
        sorted_by_dollar_volume = sorted(selected, key=lambda x: x.dollar_volume, reverse=True) 
        top = sorted_by_dollar_volume[:self._num_coarse]
        return [i.symbol for i in top]

    def _fine_selection_function(self, fine):
        # Skip if it is not the end of the quarter
        if self._reb != 3:
            return self._long + self._short
            
        self._reb = 0
            
        # Drop stocks which don't have the information on operation margin (quality factor), price change in 1 month (momentum), book value per share (value) and forward dividend.
        # you can try replacing those factor with your own factors here
        filtered_fine = [x for x in fine if x.operation_ratios.operation_margin.value and x.valuation_ratios.price_change_1m and x.valuation_ratios.book_value_per_share and x.valuation_ratios.forward_dividend]
                                        
        self.log('remained to select %d'%(len(filtered_fine)))
        
        # Rank stocks by each of the factors
        sorted_by_factor1 = sorted(filtered_fine, key=lambda x: x.operation_ratios.operation_margin.value, reverse=True)
        sorted_by_factor2 = sorted(filtered_fine, key=lambda x: x.valuation_ratios.price_change_1m, reverse=True)
        sorted_by_factor3 = sorted(filtered_fine, key=lambda x: x.valuation_ratios.book_value_per_share, reverse=True)
        sorted_by_factor4 = sorted(filtered_fine, key=lambda x: x.valuation_ratios.forward_dividend,reverse=True)
        
        stock_dict = {}
        
        # Assign a score to each stock and then rank them, equal weights were used for each of the factors here.
        for i,ele in enumerate(sorted_by_factor1):
            rank1 = i
            rank2 = sorted_by_factor2.index(ele)
            rank3 = sorted_by_factor3.index(ele)
            rank4= sorted_by_factor4.index(ele)
            score = sum([rank1*0.25,rank2*0.25,rank3*0.25,rank4*0.25])
            stock_dict[ele] = score
        
        # Sort the stocks by their overall scores
        sorted_stock = sorted(stock_dict.items(), key=lambda d:d[1],reverse=False)
        sorted_symbol = [x[0] for x in sorted_stock]

        # Store the stocks at the top of the ranking into the ones we go long on and the ones at the bottom as the ones we go short on
        self._long = [x.symbol for x in sorted_symbol[:self._num_fine]]
        self._short = [x.symbol for x in sorted_symbol[-self._num_fine:]]
    
        return self._long + self._short
    
    def _rebalance(self):
        # If this month the stock are not going to be long/short, liquidate them.
        long_short_list = self._long + self._short
        for symbol, security_holding in self.portfolio.items():
            if (security_holding.invested) and (symbol not in long_short_list):
                self.liquidate(symbol)
                
        
        # Assign each stock equally in the portfolio
        for i in self._long:
            self.set_holdings(i, 0.9/self._num_fine)
        
        for i in self._short:
            self.set_holdings(i, -0.9/self._num_fine)

        self._reb = 3