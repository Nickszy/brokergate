from brokergate.models import (
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
        checks = []
        checks.append(self._check_symbol_currency(request))
        checks.append(self._check_currency(request, account_summary))
        checks.append(self._check_quantity(request))
        checks.append(self._check_buying_power(request, account_summary))
        return checks

    @staticmethod
    def _check_symbol_currency(request: TradeOrderRequest) -> RiskCheckResult:
        symbol_upper = request.symbol.upper()
        expected_currency = "HKD" if symbol_upper.endswith(".HK") else "USD"
        if request.currency.upper() != expected_currency:
            return RiskCheckResult(
                rule_id="symbol_currency_mismatch",
                status=RiskCheckStatus.blocked,
                reason=f"Symbol market currency mismatch: symbol {request.symbol} requires currency {expected_currency}, but request specified {request.currency}.",
            )
        return RiskCheckResult(
            rule_id="symbol_currency_mismatch",
            status=RiskCheckStatus.passed,
            reason="Request currency matches symbol market currency.",
        )

    @staticmethod
    def _check_currency(
        request: TradeOrderRequest,
        account_summary: AccountSummary,
    ) -> RiskCheckResult:
        if request.currency.upper() != account_summary.base_currency.upper():
            return RiskCheckResult(
                rule_id="currency_mismatch",
                status=RiskCheckStatus.blocked,
                reason=f"Currency mismatch: request currency {request.currency} does not match account base currency {account_summary.base_currency}.",
                available_buying_power=account_summary.buying_power,
                currency=account_summary.base_currency,
            )
        return RiskCheckResult(
            rule_id="currency_mismatch",
            status=RiskCheckStatus.passed,
            reason="Order currency matches account base currency.",
            currency=account_summary.base_currency,
        )

    @staticmethod
    def _check_quantity(request: TradeOrderRequest) -> RiskCheckResult:
        if request.quantity % 1 != 0:
            return RiskCheckResult(
                rule_id="fractional_quantity_limit",
                status=RiskCheckStatus.blocked,
                reason="Fractional quantities are not supported in the MVP rule set.",
            )
        return RiskCheckResult(
            rule_id="fractional_quantity_limit",
            status=RiskCheckStatus.passed,
            reason="Quantity is integral.",
        )

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
