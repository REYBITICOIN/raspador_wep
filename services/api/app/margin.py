from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/margins", tags=["margins"])
MONEY = Decimal("0.01")


def money(value: Decimal | int | float) -> float:
    normalized = Decimal(str(value))
    return float(normalized.quantize(MONEY, rounding=ROUND_HALF_UP))


class MarginRequest(BaseModel):
    sale_price: Decimal = Field(gt=0)
    acquisition_cost: Decimal = Field(ge=0)
    commission_percent: Decimal = Field(ge=0, le=100)
    tax_percent: Decimal = Field(default=0, ge=0, le=100)
    ads_percent: Decimal = Field(default=0, ge=0, le=100)
    financing_percent: Decimal = Field(default=0, ge=0, le=100)
    fixed_fee: Decimal = Field(default=0, ge=0)
    shipping_cost: Decimal = Field(default=0, ge=0)
    packaging_cost: Decimal = Field(default=0, ge=0)
    other_cost: Decimal = Field(default=0, ge=0)
    desired_margin_percent: Decimal | None = Field(default=None, ge=0, lt=100)


@router.post("/calculate")
def calculate_margin(request: MarginRequest) -> dict:
    variable_rate = (
        request.commission_percent
        + request.tax_percent
        + request.ads_percent
        + request.financing_percent
    ) / Decimal("100")
    if variable_rate >= 1:
        raise HTTPException(422, "A soma das taxas percentuais deve ser menor que 100%")

    variable_fees = request.sale_price * variable_rate
    fixed_costs = (
        request.acquisition_cost
        + request.fixed_fee
        + request.shipping_cost
        + request.packaging_cost
        + request.other_cost
    )
    total_cost = fixed_costs + variable_fees
    net_revenue = request.sale_price - variable_fees
    contribution_margin = net_revenue - (
        request.fixed_fee
        + request.shipping_cost
        + request.packaging_cost
        + request.other_cost
    )
    net_profit = request.sale_price - total_cost
    net_margin = net_profit / request.sale_price * Decimal("100")
    roi = (
        net_profit / request.acquisition_cost * Decimal("100")
        if request.acquisition_cost > 0
        else None
    )
    markup = (
        (request.sale_price / request.acquisition_cost - Decimal("1")) * Decimal("100")
        if request.acquisition_cost > 0
        else None
    )
    break_even_price = fixed_costs / (Decimal("1") - variable_rate)

    desired_price = None
    if request.desired_margin_percent is not None:
        desired_rate = request.desired_margin_percent / Decimal("100")
        denominator = Decimal("1") - variable_rate - desired_rate
        if denominator <= 0:
            raise HTTPException(422, "Margem desejada incompatível com as taxas")
        desired_price = fixed_costs / denominator

    return {
        "sale_price": money(request.sale_price),
        "net_revenue": money(net_revenue),
        "variable_fees": money(variable_fees),
        "fixed_costs": money(fixed_costs),
        "total_cost": money(total_cost),
        "contribution_margin": money(contribution_margin),
        "net_profit": money(net_profit),
        "net_margin_percent": money(net_margin),
        "roi_percent": money(roi) if roi is not None else None,
        "markup_percent": money(markup) if markup is not None else None,
        "break_even_price": money(break_even_price),
        "desired_sale_price": money(desired_price) if desired_price is not None else None,
        "profitable": net_profit > 0,
        "fee_breakdown": {
            "commission": money(request.sale_price * request.commission_percent / Decimal("100")),
            "tax": money(request.sale_price * request.tax_percent / Decimal("100")),
            "ads": money(request.sale_price * request.ads_percent / Decimal("100")),
            "financing": money(request.sale_price * request.financing_percent / Decimal("100")),
            "fixed_fee": money(request.fixed_fee),
            "shipping": money(request.shipping_cost),
            "packaging": money(request.packaging_cost),
            "other": money(request.other_cost),
        },
        "inputs_are_user_supplied": True,
        "fee_source": "manual_until_official_quote_is_connected",
    }

