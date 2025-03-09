# Import the packages
from AlgorithmImports import *
# This code defines the contracts that we will use in our trading strategy  
class ContractsData:
    def __init__(self, classification, contract_offset):
        self.classification = classification
        self.contract_offset = contract_offset

contracts = {
    pair[0]: ContractsData(pair[1], pair[2]) for pair in [
        (Symbol.create(Futures.Currencies.EUR, SecurityType.FUTURE, Market.CME), ("Currencies", "EUR"), 0),
        (Symbol.create(Futures.Currencies.GBP, SecurityType.FUTURE, Market.CME), ("Currencies", "GBP"), 0),
        (Symbol.create(Futures.Currencies.JPY, SecurityType.FUTURE, Market.CME), ("Currencies", "JPY"), 0),
        (Symbol.create(Futures.Energies.NATURAL_GAS, SecurityType.FUTURE, Market.NYMEX), ("Energies", "Gas"), 1),
        (Symbol.create(Futures.Energies.CRUDE_OIL_WTI, SecurityType.FUTURE, Market.NYMEX), ("Energies", "Oil"), 0),
        (Symbol.create(Futures.Financials.Y_2_TREASURY_NOTE, SecurityType.FUTURE, Market.CBOT), ("Fixed Income", "Bonds"), 0),
        (Symbol.create(Futures.Financials.Y_10_TREASURY_NOTE, SecurityType.FUTURE, Market.CBOT), ("Fixed Income", "Bonds"), 0),
        (Symbol.create(Futures.Financials.Y_30_TREASURY_BOND, SecurityType.FUTURE, Market.CBOT), ("Fixed Income", "Bonds"), 0),
        (Symbol.create(Futures.Grains.CORN, SecurityType.FUTURE, Market.CBOT), ("Agricultural", "Grain"), 0),       
        (Symbol.create(Futures.Grains.SOYBEANS, SecurityType.FUTURE, Market.CBOT), ("Agricultural", "Grain"), 0),
        (Symbol.create(Futures.Grains.WHEAT, SecurityType.FUTURE, Market.CBOT), ("Agricultural", "Grain"), 0),
        (Symbol.create(Futures.Indices.SP_500_E_MINI, SecurityType.FUTURE, Market.CME), ("Equity", "US"), 0),
        (Symbol.create(Futures.Indices.NASDAQ_100_E_MINI, SecurityType.FUTURE, Market.CME), ("Equity", "US"), 0),
        (Symbol.create(Futures.Indices.RUSSELL_2000_E_MINI, SecurityType.FUTURE, Market.CME), ("Equity", "US"), 0),
        (Symbol.create(Futures.Indices.VIX, SecurityType.FUTURE, Market.CFE), ("Volatility", "US"), 0),       
        (Symbol.create(Futures.Metals.COPPER, SecurityType.FUTURE, Market.COMEX), ("Metals", "Industrial"), 0),
        (Symbol.create(Futures.Metals.GOLD, SecurityType.FUTURE, Market.COMEX), ("Metals", "Precious"), 0),
        (Symbol.create(Futures.Metals.SILVER, SecurityType.FUTURE, Market.COMEX), ("Metals", "Precious"), 0)        
    ]
}