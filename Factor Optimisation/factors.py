# Import the required packages
from AlgorithmImports import *

# Here we create multiple classes to define each of the factors that will be used in the optimisation process.
# In this case we are using the Fama French 5 factors with the following proxies.
# MKT - Value given by book value per share
# SMB - Size given by total equity
# HML - Quality given by operating profit margin
# RMW - Profitability given by ROE
# CMA - Investment pattern given by total assets growth

class MKT:
    def __init__(self, security):
        self._security = security

    @property
    def value(self):
        return self._security.fundamentals.valuation_ratios.book_value_per_share


class SMB:
    def __init__(self, security):
        self._security = security

    @property
    def value(self):
        return self._security.fundamentals.financial_statements.balance_sheet.total_equity.value

class HML:
    def __init__(self, security):
        self._security = security

    @property
    def value(self):
        return self._security.fundamentals.operation_ratios.operation_margin.value

class RMW:
    def __init__(self, security):
        self._security = security

    @property
    def value(self):
        return self._security.fundamentals.operation_ratios.ROE.value

class CMA:
    def __init__(self, security):
        self._security = security

    @property
    def value(self):
        return self._security.fundamentals.operation_ratios.total_assets_growth.value
