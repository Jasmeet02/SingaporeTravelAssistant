import requests
from mcp.server.fastmcp import FastMCP

print("=== CURRENCY SERVER STARTED ===")
mcp = FastMCP(
    "Currency Server",
    instructions=(
        "This MCP server provides currency-conversion tools. "
        "Use convert_currency to convert an amount from one currency to another."
    ),
)


@mcp.tool(description="""
Convert an amount from one currency to another using the Frankfurter service.

When providing results, indicate that the data came from this MCP tool.
""")
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Return the conversion details for a currency pair."""
    print("From:", from_currency)
    print("To:", to_currency)
  
    print("Amount:", amount)
   
    response = requests.get(
        "https://api.frankfurter.app/latest",
        params={"amount": amount, "from": from_currency.upper(), "to": to_currency.upper()},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    rates = payload.get("rates", {})
    rate = next(iter(rates.values())) if rates else None
    print(payload)

    print("RATE VALUE:", rate)
    converted_amount = next(iter(rates.values())) if rates else None

    if converted_amount is None:
     return {
        "error": f"No rate available for {from_currency.upper()} to {to_currency.upper()}"
    }

    exchange_rate = converted_amount / amount

    return {
      "from_currency": from_currency.upper(),
      "to_currency": to_currency.upper(),
      "amount": amount,
      "converted_amount": round(converted_amount, 2),
      "rate": round(exchange_rate, 6),
      "updated_at": payload.get("date"),
      "mcp_server_name": "Currency MCP Server",
      "data_source": "Frankfurter API"
}


if __name__ == "__main__":
    mcp.run()
