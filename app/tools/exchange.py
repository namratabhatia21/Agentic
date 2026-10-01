from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


class ExchangeInput(BaseModel):
    base: str = Field(default="EUR", pattern=r"^[A-Za-z]{3}$", description="ISO currency code.")
    symbols: list[str] = Field(
        default_factory=list,
        description="Target ISO currency codes, e.g. ['USD', 'INR']. Empty = all available.",
        max_length=30,
    )
    amount: float = Field(default=1.0, gt=0, description="Amount of the base currency.")


async def _rates(inp: ExchangeInput, ctx: ToolContext) -> str:
    params: dict = {"base": inp.base.upper(), "amount": inp.amount}
    if inp.symbols:
        params["symbols"] = ",".join(s.upper() for s in inp.symbols)
    data = await ctx.cached_get_json(FRANKFURTER_URL, params)
    rates = data.get("rates")
    if not rates:
        raise ToolError(f"No rates returned: {data}")
    body = ", ".join(f"{k}: {v}" for k, v in sorted(rates.items()))
    return f"{data.get('amount')} {data.get('base')} on {data.get('date')} (ECB reference) = {body}"


exchange_rates = Tool(
    name="get_exchange_rates",
    description="Latest European Central Bank currency exchange rates; also converts amounts.",
    input_model=ExchangeInput,
    handler=_rates,
)
