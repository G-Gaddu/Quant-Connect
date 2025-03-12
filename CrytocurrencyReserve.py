# First import the required packages

from AlgorithmImports import *
import scipy.cluster.hierarchy as sch
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
import numpy as np
import random

class TrumpCryptoReservePortfolio(QCAlgorithm):
    # Initialise the class that will carry out the investment strategy
    def initialize(self) -> None:
        # Set the start and end date
        self.set_start_date(2017, 3, 10)
        self.set_end_date(2025, 3, 10)
        # Set the strategy cash
        self.set_cash(1000000000)

        # Then we obtain all the Crypto pairs that are listed on coinbase that are not stablecoin and are quoted in USD

        self._crypto_pairs = [
            a.key.symbol 
            for a in self.symbol_properties_database.get_symbol_properties_list(Market.COINBASE) 
            if (a.value.market_ticker.split('-')[0] not in ['FRAX', 'DAI', 'BUSD', 'TUSD', 'USDP', 'FDUSD', 'USDT', 'USDC'] and 
                a.value.quote_currency == self.account_currency)  
        ]
        
        # Then we define our universe of cryptocurrencies that are updated at the start of each month
        update_period = self.date_rules.month_start()
        self.time_rules.set_default_time_zone(TimeZones.UTC)
        self.universe_settings.schedule.on(update_period)
        self.universe_settings.resolution = Resolution.DAILY
        self._universe = self.add_universe(CryptoUniverse.coinbase(self._selected_crypto))
        
        # Rebalance the portfolio at the start of each month at midnight
        self.schedule.on(update_period, self.time_rules.midnight, self._rebalance_portfolio)
        # Apply the Heirarchicial Risk Parity (HRP) Approach to obtain the allocations for the portfolio
        self._HierRP = HeirarchicalRiskParity(self, self.get_parameter('lookback_months', 12)*30)

    # Define a function that will assign weights to crypto portfolio based on HRP Approach
    def _rebalance_portfolio(self):
        symbols = self._universe.selected
        if not symbols:
            return
        self.set_holdings([PortfolioTarget(ticker, 0.9*weight) for ticker, weight in self._HierRP.allocation(symbols).items()], True)
        
    # Define a function that will select the crytocurrencies in crypto_pairs and then sort them by volume, take only the 5 largest
    def _selected_crypto(self, data):
        chosen_crypto = [x for x in data if str(x.symbol.id).split()[0] in self._crypto_pairs]
        chosen_crypto = [x.symbol for x in sorted(chosen_crypto, key=lambda x: x.volume_in_usd)[-5:]]
        self.plot('Cryto Investment Universe', 'Size of Cryptocurrency', len(chosen_crypto))
        return chosen_crypto

# Create a class to carry out the Hierarchical Risk Parity optimisation
class HeirarchicalRiskParity:
    # Initialise the class
    def __init__(self, algorithm, lookback=365):
        self._algorithm = algorithm
        self._lookback = lookback

    # Determine the variance for each cluster
    def _cluster_variance(self, cov_mat, cluster_items):
        cluster_cov_arr = cov_mat.loc[cluster_items, cluster_items] 
        weights = self._inverse_variance_portfolio_wgts(cluster_cov_arr).reshape(-1, 1)
        return np.dot(np.dot(weights.T, cluster_cov_arr), weights)[0, 0]

    # Determine the inverse variance portfolio
    def _inverse_variance_portfolio_wgts(self, cov_mat, **kargs):
        inverse_var_mat = 1 / np.diag(cov_mat)
        return inverse_var_mat / inverse_var_mat.sum()    
    
    # Function to obtain a distance matrix based on the correlation of the prices between assets
    def _distance_matrix(self, corr_mat):
        return ((1 - corr_mat) / 2.0) ** 0.5 

    # Function to determine the weights of the portfolio
    def allocation(self, symbols):
        # First we group the assets based on their daily returns
        daily_rets = self._algorithm.history(symbols, self._lookback, Resolution.DAILY).close.unstack(0).pct_change()[1:]
        corr_mat, cov_mat = daily_rets.corr(), daily_rets.cov()
        euc_distance = self._distance_matrix(corr_mat)
        linkage = sch.linkage(squareform(euc_distance), 'single')
        # Apply quasi-diagonalization and retrieve the labels
        sort_ix = self._quasi_diagonalization(linkage)
        sort_ix = corr_mat.index[sort_ix].tolist() 
        # Finally apply recursive bisection
        return self._recursive_bisection(cov_mat, sort_ix)

    # Function to perform quasi diagonalisation
    def _quasi_diagonalization(self, linkage):
        # Convert to integer format and determine the number of original items 
        linkage = linkage.astype(int)
        sorted_ix = pd.Series([linkage[-1, 0], linkage[-1, 1]])
        items = linkage[-1, 3] 
        # Break down the clusters and continue to do so, relabelling them in the process until 
        # we are back at the original components
        while sorted_ix.max() >= items:
            sorted_ix.index = range(0, sorted_ix.shape[0] * 2, 2) 
            df0 = sorted_ix[sorted_ix >= items] 
            i = df0.index
            j = df0.values - items
            sorted_ix[i] = linkage[j, 0] 
            df0 = pd.Series(linkage[j, 1], index=i+1)
            sorted_ix = pd.concat([sorted_ix, df0]) 
            sorted_ix = sorted_ix.sort_index() 
            sorted_ix.index = range(sorted_ix.shape[0]) 
        return sorted_ix.tolist()

    # Define a function to carry out recursive bisection
    def _recursive_bisection(self, cov_mat, sort_ix):
        # Determine the allocation via HRP
        alloca = pd.Series(1.0, index=sort_ix)
        # Place all the items in one cluster
        num_clusters = [sort_ix] 
        while len(num_clusters) > 0:
            # Perform bisection. Drop any elements in a 1 element list. For multi element lists, split them into two
            bisected_clusters = []
            for x in num_clusters:
                if len(x) > 1:
                    for y, z in ((0, len(x) / 2), (len(x) / 2, len(x))):
                        bisected_clusters.append(x[int(y):int(z)])
            num_clusters = bisected_clusters
            for i in range(0, len(num_clusters), 2): # Parse the pairs of clusters
                # Obtain the first and second clusters of each pair
                cluster_1 = num_clusters[i] 
                cluster_2 = num_clusters[i+1] 
                c_var_1 = self._cluster_variance(cov_mat, cluster_1)
                c_var_2 = self._cluster_variance(cov_mat, cluster_2)
                alpha = 1 - c_var_1 / (c_var_1 + c_var_2)
                # Obtain the weight of each cluster
                alloca[cluster_1] *= alpha 
                alloca[cluster_2] *= 1 - alpha 
        return alloca

