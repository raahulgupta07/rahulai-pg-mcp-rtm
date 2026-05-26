"""Default classification rule parameters. Seeds /api/rule-config when no
saved data/rule_config.json exists. Admins tune these in the /rules page;
the classification engine and AI service read them at run time."""

DEFAULT_RULES = {
    "pareto": {
        "class_a_cutoff": 80,          # cumulative %-ceiling for Class A
        "class_b_cutoff": 95,          # cumulative %-ceiling for Class B (rest = C)
    },
    "wholesaler": {
        "enabled": True,
        "cartons_per_brand_month": 3,  # >= this many cartons → wholesaler (F4)
        "item_type": "Local",          # item type counted toward the carton rule
    },
    "category_override": {
        "enabled": True,
        "contribution_cutoff": 80,     # category contribution-% → Class A {category}
    },
    "frequency": {
        "class_a_tier": "F4",          # visit tier assigned to Class A outlets
        "other_tier": "F2",            # visit tier assigned to everyone else
    },
    "workload": {
        "yangon_min": 25, "yangon_max": 30,
        "regional_min": 30, "regional_max": 35,
    },
    "growth": {
        "growing_pct": 10,             # 6M vs ½·12M above this %  → Growing
        "declining_pct": 10,           # 6M vs ½·12M below this %  → Declining
    },
    "risk": {
        "freq_medium_days": 30,        # buy gap > this → +1 risk signal
        "freq_high_days": 60,          # buy gap > this → +1 more signal
        "low_purchase_days": 5,        # purchase days < this → +1 signal
        "signals_for_high": 3,         # >= signals → High risk
        "signals_for_medium": 1,       # >= signals → Medium risk
    },
    "ai": {
        "llm_enabled": True,           # use the LLM when an API key is present
        "temperature": 0.3,            # LLM creativity (0 = deterministic, 1 = loose)
        "enrich_top_n": 15,            # per-outlet LLM insight for the top N outlets
        # NOTE: the model + provider URL are set by the super-admin in Settings,
        # not here — see data/settings.json (llm_model / llm_base_url).
    },
}


def merge_rules(saved: dict) -> dict:
    """Deep-merge a saved (possibly partial) config over the defaults so a
    missing key never crashes the engine."""
    out = {}
    for section, vals in DEFAULT_RULES.items():
        merged = dict(vals)
        if isinstance(saved, dict) and isinstance(saved.get(section), dict):
            for k, v in saved[section].items():
                if k in merged:
                    merged[k] = v
        out[section] = merged
    return out
