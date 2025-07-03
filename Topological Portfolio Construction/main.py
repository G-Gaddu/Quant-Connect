# Import the required packages
from AlgorithmImports import *
from topological_universe_selection import TopologicalUniverseSelection

# Initialise the random seed
np.random.seed(42)

class TopologicalPortfolio(QCAlgorithm):
    def initialize(self) -> None:
        # Set a start date, end date and the cash allocated to the strategy
        self.set_start_date(2020, 7, 1)
        self.set_end_date(2025, 7, 1)
        self.set_cash(10000000)

        # Set the benchmark to the S&P500 (it will also be our initial investment universe)
        sp500 = self.add_equity("SPY").symbol
        self.set_benchmark(sp500)

        # We define the lookback period to construct and analyse our topological structure, then we define a period to reconstruct the topological complex
        lookback_period = self.get_parameter("lookback_period", 150)
        recalibration_period = self.get_parameter("recalibration_period", 125)
        self.universe_topologicalmodel = TopologicalUniverseSelection(sp500, lookback_period, recalibration_period, lambda u: [x.symbol for x in sorted([x for x in u if x.weight], key=lambda x: x.weight, reverse=True)[:200]])
        self.add_universe_selection(self.universe_topologicalmodel)

        # Then schedule the portfolio to be rebalanced on a daily basis
        self.schedule.on(self.date_rules.every_day(sp500), self.time_rules.at(9, 31), self.rebalance)

        # Finally, set a warm up period of 1 year
        self.set_warm_up(timedelta(365))

    def rebalance(self) -> None:
        # First check if there are any clusters in the investment universe
        if self.universe_topologicalmodel.clustered_symbols:
            # Then determine the weights allocated to each cluster
            wghts = self.wght_allocation(self.universe_topologicalmodel.clustered_symbols)
            # Then rebalance the portfolio based on the clustered weights
            self.set_holdings([PortfolioTarget(symbol, wght) for symbol, wght in wghts.items()], liquidate_existing_holdings=True)

    def wght_allocation(self, clustered_symbols):
        # Assign weights to the clusters. Do note invest in any outliers
        # Initialise a dictionary to store the weights
        wghts = {}
        # Define a function that will allocate weights
        def allocate_wghts(nested_list, level=1):
            # Determine the length of the list of stocks
            len_list = len(nested_list)
            # If the length is 0 then return
            if len_list == 0:
                return
            # Assign an initial equal weight per element
            wght_per_elmnt = 1 / len_list
            # Loop over the list, if an item is in the list then the function is recursively called to the subcluster
            # Otherwise it is a single stock and the weight is determined and added to the dictionary
            for item in nested_list:
                if isinstance(item, list):
                    allocate_wghts(item, level + 1)
                else:
                    wghts[item] = wghts.get(item, 0) + wght_per_elmnt / (2 ** (level - 1))
        # Determine the overall weights
        allocate_wghts(clustered_symbols)
        return pd.Series(wghts) / sum(wghts.values())