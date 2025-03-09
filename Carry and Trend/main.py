# Import the required packages
from AlgorithmImports import *
from insights import CarryTrendAlpha
from buffered_portfolio import PortfolioConstruction
from selection import FutureSelection
from weights import GetWeights

class CarryAndTrend(QCAlgorithm):

    excluded_tickers_from_last_iteration = []
    validated_tickers_from_previous_iteration = False

    def initialize(self):
        # Define the start and end dates and set the cash
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(10000000)

        # Define our brokerage model and account type, initiliase the settings and define the minimum order margin portfolio percentage
        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)
        self.set_security_initializer(BrokerageModelSecurityInitializer(self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices)))        
        self.settings.minimum_order_margin_portfolio_percentage = 0
        
        # For the data normalisation we use the backwards panama canal to eliminate price jumps between 2 consecutive contracts
        self.universe_settings.data_normalization_mode = DataNormalizationMode.BACKWARDS_PANAMA_CANAL
        
        # Map contracts on the first date of the delivery month of the front month.
        self.universe_settings.data_mapping_mode = DataMappingMode.LAST_TRADING_DAY
        self.add_universe_selection(FutureSelection())

        self.add_alpha(CarryTrendAlpha(
            self,
            self.get_parameter("emac_value", 6), 
            self.get_parameter("abs_forecast_limit", 20),           
            self.get_parameter("sigma_range", 32),
            self.get_parameter("risk_limit", 0.2),               
            self.get_parameter("blend_years", 3) 
        ))
        
        # We won't rebalance the portfolio if there are any changes in the insights or securities

        self.settings.rebalance_portfolio_on_security_changes = False
        self.settings.rebalance_portfolio_on_insight_changes = False
        self.total = 0
        self.day = -1
        
        # Create our portfolio with a rebalancing function
        self.set_portfolio_construction(PortfolioConstruction(
            self.rebalance_portfolio,
            self.get_parameter("buffer_value", 0.1)              # Hardcoded on p.167 & p.173
        ))

        # Immediate execution to ensure that only orders are made based on the alpha model, if the portfolio value falls by 10% then liquidate
        self.set_execution(ImmediateExecutionModel())
        self.add_risk_management(NullRiskManagementModel())
        

        # We need several years of data to warm-up the algorithm
        self.set_warm_up(self.start_date - datetime(2016, 1, 1)) 

    # Create a rebalancing function to rebalance the portfolio
    def rebalance_portfolio(self, time):
        if not self.is_warming_up and self.current_slice.quote_bars.count > 0 and (self.total != self.insights.total_count or self.day != self.time.day):
            self.total = self.insights.total_count
            self.day = self.time.day
            return time
        return None

    def on_data(self, data):
        # Exit positions that aren't backed by existing insights.
        # First check we are not in the warming up period
        if not self.validated_tickers_from_previous_iteration and not self.is_warming_up:
            for security_holding in self.portfolio.Values:
                if not security_holding.invested:
                    continue
                ticker = security_holding.symbol
                if not self.insights.has_active_insights(ticker, self.utc_time):
                    self.excluded_tickers_from_last_iteration.append(symbol)
            self.validated_tickers_from_previous_iteration = True
       
        for ticker in self.excluded_tickers_from_last_iteration[:]:
            if self.is_market_open(ticker):
                self.liquidate(ticker, tag="Holding from last iteration, to be liquidated")
                self.excluded_tickers_from_last_iteration.remove(ticker)
