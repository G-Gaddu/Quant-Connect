# Import the required packages
import kmapper as km
from AlgorithmImports import *
from Selection.ETFConstituentsUniverseSelectionModel import ETFConstituentsUniverseSelectionModel
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from umap import UMAP

# Initialise the random seed
np.random.seed(42)

class TopologicalUniverseSelection(ETFConstituentsUniverseSelectionModel):
    # Initialise the class
    def __init__(self, etf_ticker: Symbol, lookback_period: int = 250, recalibration_period: timedelta = None, universe_filter_func: Callable[list[ETFConstituentUniverse], list[Symbol]] = None) -> None:
        self.clustered_symbols = None
        self.lookback_period = lookback_period
        self.recalibration_period = recalibration_period
        self._ticker = etf_ticker
        super().__init__(etf_ticker, None, universe_filter_func)

    def create_universes(self, algorithm: QCAlgorithm) -> list[Universe]:
        list_of_universes = super().create_universes(algorithm)
        # Warm up the investment universe, gather the tickers when the market next opens at 9:31 in the morning
        market_open = algorithm.securities[self._ticker].exchange.hours.get_next_market_open(algorithm.time, False)
        algorithm.schedule.on(algorithm.date_rules.on([market_open]), algorithm.time_rules.at(9, 31), lambda: self.obtain_graph_symbols(algorithm))
        return list_of_universes

    def obtain_graph_symbols(self, algorithm: QCAlgorithm) -> None:
        # We first construct a simplicial complex
        graph, ticker_list = self.obtain_simplicial_complex(algorithm, self.lookback_period)
        # If the ticker list is not empty then we can perform the clustering
        if len(ticker_list) > 0:
            self.clustered_symbols = self.clustering_tickers(graph, ticker_list)
        # Then schedule a time to reconstruct the topological structure
        algorithm.schedule.on(algorithm.date_rules.on([algorithm.time + timedelta(self.recalibration_period)]), algorithm.time_rules.at(0, 1), lambda: self.obtain_graph_symbols(algorithm))

    def obtain_simplicial_complex(self, algorithm: QCAlgorithm, lookback_period: int) -> tuple[dict[str, object], list[Symbol]]:
        # If the investment universe is blank then return nothing
        if not self.universe.selected:
            return {}, []
        # First obtain the stock prices of each S&P500 constituent
        stock_prices = algorithm.history(self.universe.selected, lookback_period, Resolution.DAILY).unstack(0).close
        # Then determine the log returns of each stock
        log_rets = np.log(stock_prices / stock_prices.shift(1)).dropna().T
        # If the log returns are empty then return nothing
        if log_rets.empty:
            return {}, []
        # Then initialise the Keppler Mapper algorithm
        mapper = km.KeplerMapper()
        # We then project the data into a 2d subspace using 2 transformations: PCA and UMAP. PCA is used as it can retain the most variance in the data
        # UMAP is used as it addresses non linear relationships well and preserves local and global structures
        projected_stock_data = mapper.fit_transform(log_rets, projection=[PCA(n_components=0.8, random_state=1), UMAP(n_components=1, random_state=1, n_jobs=-1)])
        # Then cluster the data with DBSCAN (it is used as it can better handle noise, the correlation distance to cluster is important for forming portfolios
        final_graph = mapper.map(projected_stock_data, log_rets, clusterer=DBSCAN(metric='correlation', n_jobs=-1))
        return final_graph, stock_prices.columns

    def clustering_tickers(self, graph: dict[str, object], ticker_list: list[Symbol]) -> list[list[object]]:
        # Initialise the list of joined clusters
        joined_clusters = []
        # Loop over each pair in the links section of the graph dictionary
        for a, b in graph['links'].items():
            # If a and b are already part of an existing cluster set the flag to False
            isin = False
            # Loop over the existing clusters
            for n in range(len(joined_clusters)):
                # Check if a or b are part of an existing cluster, if so then merge joined cluster with a and b and set the flag to True
                if a in joined_clusters[n] or b in joined_clusters[n]:
                    joined_clusters[n] = list(set(joined_clusters[n] + [a] + b))
                    isin = True
            # If isin is True then continue
            if isin:
                continue
            joined_clusters.append([a] + b)
        # Add any nodes from the graph that have not already been included in a joined cluster as a single cluster
        joined_clusters += [[a] for a in graph['nodes'] if a not in [c for b in joined_clusters for c in b]]
        # Finally convert the node into a symbol
        return [[list([ticker_list[graph['nodes'][a]]][0]) for a in joined_cluster] for joined_cluster in joined_clusters]