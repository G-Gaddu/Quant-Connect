# Import the required packages
from AlgorithmImports import *
from Selection.FutureUniverseSelectionModel import FutureUniverseSelectionModel
from futures_contracts import contracts

class FutureSelection(FutureUniverseSelectionModel):
    def __init__(self) -> None:
        # Update the investment universe on a daily basis
        # Set the method responsible for selecting tickers
        super().__init__(timedelta(1), self.select_future_tickers)
        self.symbols = list(contracts.keys())

        # Select contracts that expire in less than 12 months 
    def expiry_filter(self, filter: FutureFilterUniverse) -> FutureFilterUniverse:
        return filter.expiration(0, 365)
    
    # Get the tickers for the contracts
    def select_future_tickers(self, utc_time: datetime) -> List[Symbol]:
        return self.symbols
