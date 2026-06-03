from openbroker.models import (
    AccountSummary,
    OrderSide,
    OrderType,
    RiskCheckResult,
    RiskCheckStatus,
    TradeOrderRequest,
)


class RiskEngine:
    def evaluate_order(
        self,
        request: TradeOrderRequest,
        account_summary: AccountSummary,
    ) -> list[RiskCheckResult]:
        return [self._check_buying_power(request, account_summary)]

    @staticmethod
    def _check_buying_power(
        request: TradeOrderRequest,
        account_summary: AccountSummary,
    ) -> RiskCheckResult:
        if request.side != OrderSide.buy:
            return RiskCheckResult(
                rule_id="buying_power_limit",
                status=RiskCheckStatus.passed,
                reason="Sell orders do not consume buying power in the MVP rule set.",
                available_buying_power=account_summary.buying_power,
                currency=account_summary.base_currency,
            )

        if request.order_type == OrderType.market or request.limit_price is None:
            return RiskCheckResult(
                rule_id="buying_power_limit",
                status=RiskCheckStatus.blocked,
                reason="Buy order cannot be checked without a deterministic price.",
                available_buying_power=account_summary.buying_power,
                currency=account_summary.base_currency,
            )

        required_amount = request.quantity * request.limit_price
        if required_amount > account_summary.buying_power:
            return RiskCheckResult(
                rule_id="buying_power_limit",
                status=RiskCheckStatus.blocked,
                reason="Estimated buy amount exceeds account buying power.",
                required_amount=required_amount,
                available_buying_power=account_summary.buying_power,
                currency=account_summary.base_currency,
            )

        return RiskCheckResult(
            rule_id="buying_power_limit",
            status=RiskCheckStatus.passed,
            reason="Estimated buy amount is within account buying power.",
            required_amount=required_amount,
            available_buying_power=account_summary.buying_power,
            currency=account_summary.base_currency,
        )


risk_engine = RiskEngine()
