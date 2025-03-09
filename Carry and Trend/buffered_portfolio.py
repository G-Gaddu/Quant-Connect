# Import the required packages
from AlgorithmImports import *

# This script creates a portfolio that adjusts positions based on insights and minimizing trading churn
class PortfolioConstruction(EqualWeightingPortfolioConstructionModel):

    def __init__(self, rebalance, buffer_value):
        # Initialise the class
        super().__init__(rebalance)
        self.buffer_value = buffer_value

    def create_targets(self, algorithm: QCAlgorithm, insights: List[Insight]) -> List[PortfolioTarget]:
        targets = super().create_targets(algorithm, insights)
        updated_targets = []
        for item in insights:
            contract = algorithm.securities[item.symbol]
            best_position = contract.forecast * contract.position / 10

            # To reduce churn we create a buffer zone 
            buffer_range = self.buffer_value * abs(contract.position)
            lower_limit = round(best_position - buffer_range)
            upper_limit = round(best_position + buffer_range)
            
            # Determine the amount put in the buffer zone
            holdings_amt = contract.holdings.quantity
            if lower_limit <= holdings_amt <= upper_limit:
                continue
            amount = lower_limit if holdings_amt < lower_limit else upper_limit

            # Place trades
            updated_targets.append(PortfolioTarget(item.symbol, amount))
        
        # Liquidate contracts that have an expired insight
        for item in targets:
            if item.quantity == 0:
                updated_targets.append(item)

        return updated_targets

    