import numpy as np
from sharadar.pipeline.engine import symbol
from sharadar.pipeline.factors import beta_residual
from zipline.pipeline import CustomFactor
from zipline.pipeline.data import USEquityPricing


class Closes(CustomFactor):
    inputs = [USEquityPricing.close]
    window_safe = True
    window_length = 1

    #__name__ = "Closes()"

    def compute(self, today, assets, out, close):
        out[:] = close[-self.window_length]


def prices_by_sid(assets, close, sid):
    rate_index = np.where((assets == sid) == True)[0][0]
    rate = np.reshape(close[:, rate_index], (-1, 1))
    return rate

class TBillBeta(CustomFactor):
    inputs = [USEquityPricing.close, Closes()[symbol('TR3M')]]
    window_safe = True
    window_length = 252

    def compute(self, today, assets, out, close, rate):
        # monthly log returns
        monthly_r = np.diff(np.log(close[0::21, :]), axis=0)
        # To go from log return to simple return
        monthly_R = np.exp(monthly_r) - 1.0
        # The T-Bill rate is annualy, therefore we need to annualise
        R = (1.0 + monthly_R) ** 12 - 1.0

        # Treasury Bonds rates every 21 daily
        t_rates = rate[0::21, :][1:, :]

        beta = beta_residual(R, t_rates, standardize=True)[0]
        out[:] = beta


class TBillBondSpreadBeta(CustomFactor):
    """
    the difference in the returns to 20y and 3m government bonds,
    """
    inputs = [USEquityPricing.close]
    window_safe = True
    window_length = 252

    def compute(self, today, assets, out, close):
        # monthly log returns
        monthly_r = np.diff(np.log(close[0::21, :]), axis=0)
        # To go from log return to simple return
        monthly_R = np.exp(monthly_r) - 1.0
        # The T-Bill rate is annualy, therefore we need to annualise
        R = (1.0 + monthly_R) ** 12 - 1.0

        t_bond_30y = prices_by_sid(assets, close, 10240)
        t_bill_3m = prices_by_sid(assets, close, 10003)
        t_rates = t_bond_30y[0::21, :][1:, :] - t_bill_3m[0::21, :][1:, :]

        beta = beta_residual(R, t_rates, standardize=True)[0]
        out[:] = beta

class PurchaseManagerIndexBeta(CustomFactor):
    inputs = [USEquityPricing.close]
    window_safe = True
    window_length = 252

    def compute(self, today, assets, out, close):
        # 10430	Purchasing Managers Index
        pmi = prices_by_sid(assets, close, 10430)

        monthly_close = np.diff(np.log(close[0::21, :]), axis=0)
        monthly_rate = np.diff(np.log(pmi[0::21, :]), axis=0)

        beta = beta_residual(monthly_close, monthly_rate, standardize=True)[0]

        out[:] = beta


class InterestRate(CustomFactor):
    inputs = [Closes()[symbol('TR1Y')]]
    window_safe = True
    window_length = 1

    def compute(self, today, assets, out, int_rate):
        out[:] = int_rate[-self.window_length]


class InflationRate(CustomFactor):
    inputs = [USEquityPricing.close]
    window_safe = True
    window_length = 1

    def compute(self, today, assets, out, prices):
        # 10450	US Inflation Rates YoY
        idx = np.where((assets == 10450) == True)[0][0]
        rate = np.reshape(prices[:, idx], (-1, 1))

        out[:] = rate[-self.window_length]


class InflationRateBeta(CustomFactor):
    inputs = [
        USEquityPricing.close,
        InflationRate()
    ]
    window_safe = True
    window_length = 252

    def compute(self, today, assets, out, close, rateinf):
        monthly_close = np.diff(np.log(close[0::21, :]), axis=0)
        monthly_rateinf = rateinf[0::21, :][1:, :]
        beta = beta_residual(monthly_close, monthly_rateinf, standardize=True)[0]

        out[:] = beta


def adjust_for_inflation(rate, len, rateint, rateinf):
    interest_rate = rateint[-len] / 100.0
    inflation_rate = rateinf[-len] / 100.0
    return ((1.0 + rate) / (1.0 + interest_rate) - 1.0) / (1.0 + inflation_rate)