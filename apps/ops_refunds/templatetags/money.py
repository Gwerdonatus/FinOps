from decimal import Decimal

from django import template

register = template.Library()


def format_money(amount, currency):
    currency = str(currency).upper()
    if currency not in {"USD", "EUR", "GBP", "NGN", "JPY"}:
        return f"{amount} {currency} (minor units)"
    exponent = 0 if currency == "JPY" else 2
    value = Decimal(str(amount)) / (10**exponent)
    return f"{value:,.{exponent}f} {currency}"


@register.filter
def money(record):
    return format_money(record.amount, record.currency)
