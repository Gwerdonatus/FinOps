from django import template

register = template.Library()

RISK_CLASS = {
    "SAFE": "bg-emerald-100 text-emerald-800 ring-emerald-200",
    "DUE_SOON": "bg-amber-100 text-amber-800 ring-amber-200",
    "AT_RISK": "bg-orange-100 text-orange-800 ring-orange-200",
    "OVERDUE": "bg-red-100 text-red-800 ring-red-200",
}

SEVERITY_CLASS = {
    "info": "bg-sky-100 text-sky-800 ring-sky-200",
    "warning": "bg-amber-100 text-amber-800 ring-amber-200",
    "danger": "bg-red-100 text-red-800 ring-red-200",
}


@register.filter
def risk_badge_class(risk_state: str) -> str:
    return RISK_CLASS.get(risk_state, "bg-slate-100 text-slate-800 ring-slate-200")


@register.filter
def severity_badge_class(severity: str) -> str:
    return SEVERITY_CLASS.get(severity, "bg-slate-100 text-slate-800 ring-slate-200")
