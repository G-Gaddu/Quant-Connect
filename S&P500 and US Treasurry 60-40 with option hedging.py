from AlgorithmImports import *

# We look at the classic 60/40 investment portfolio using 60% stocks and 40% bonds. Stocks are represented by an ETF for the S&P
# 500, UPRO that attempts to provide 3 times the daily long exposure for the S&P 500. Bonds are represented by TMF, an ETF that
# aims to return 3 times the daily returns of the ICE US Treasury 20+ year bond index. The strategy is hedged with VIX options.

# The strategy first invests 0-100 basis points in calls then invests the remainder in the 60 to 40 ratio. Options are purchased
# at 135% of the moneyness of the underlying price. An equal amount is purchased in 1, 2, 3 and 4 month VIX call options.
# If the VIX Index is between 15 and 30 then the calls will form 1% of the portfolio, if the index is over 50 or under 15 then
# it will form 0.5%. Each month, on the day before expiration, the options are rolled to the appropriate expiry, call options 
# are purchased at the ask price and sold at the bid price to maintain conservative assumptions. The options are held to maturity and 
# closed on Tuesday afternoon (VIX futures and options expire on Wednesday morning). If the contracts have any 
# intrinsic value, they are sold at the bid price, and the cash is reinvested in the stock/bond portion of the portfolio.
import numpy as np

class PortfolioHedgingUsingVIXOptions(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2014, 1, 1)
        self.SetCash(1000000)
        
        data = self.AddEquity("UPRO", Resolution.Minute)
        data.SetLeverage(7)
        self.spy = data.Symbol
        
        data = self.AddEquity("TMF", Resolution.Minute)
        data.SetLeverage(7)
        self.ief = data.Symbol
        
        self.vix = 'VIX'
        
        option = self.AddIndexOption('VIX', Resolution.Minute)
        option.SetFilter(-20, 20, 25, 35)
        
    def OnData(self,slice):
        for i in slice.OptionChains:
            chains = i.Value

            # Maximum of 2 positions- UPRO and TMF are opened. That means the option has expired.
            invested = [x.Key for x in self.Portfolio if x.Value.Invested]
            if len(invested) <= 2:
                calls = list(filter(lambda x: x.Right == OptionRight.Call, chains))
                
                if not calls: return
            
                underlying_price = self.Securities[self.vix].Price
                expiries = [i.Expiry for i in calls]
                
                # Determine expiration date nearly one month.
                expiry = min(expiries, key=lambda x: abs((x.date() - self.Time.date()).days - 30))
                strikes = [i.Strike for i in calls]
                
                # Determine out-of-the-money strike.
                otm_strike = min(strikes, key = lambda x:abs(x - (float(1.35) * underlying_price)))
                otm_call = [i for i in calls if i.Expiry == expiry and i.Strike == otm_strike]
        
                if otm_call:
                    # Option weighting.
                    weight = 0.0
                    
                    if underlying_price >= 15 and underlying_price <= 30:
                        weight = 0.01
                    elif underlying_price > 30 and underlying_price <= 50:
                        weight = 0.005
                      
                    if weight != 0: 
                        option_price = otm_call[0].AskPrice
                        if np.isnan(option_price) or option_price <= 0:
                                for call in calls:
                                    option_price = call.AskPrice
                                    if not (np.isnan(option_price) or option_price <= 0):
                                        break
                        options_q = int((self.Portfolio.MarginRemaining * weight) / (option_price * 100))
    
                        # Set max leverage.
                        self.Securities[otm_call[0].Symbol].MarginModel = BuyingPowerModel(5)
                        
                        # Buy out-the-money call.
                        self.Buy(otm_call[0].Symbol, options_q)
                        
                        self.SetHoldings(self.spy, 0.60)
                        self.SetHoldings(self.ief, 0.40)