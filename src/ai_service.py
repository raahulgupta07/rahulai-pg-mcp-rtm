#!/usr/bin/env python3
"""
AI Service - Auto-generate all insights during pipeline using Gemini Flash Lite via OpenRouter.
Adds per-outlet AI columns for Excel export.
"""

import os
import json
import requests
import pandas as pd
import numpy as np
from typing import Optional, Dict


class AIService:
    """LLM + rule-based insights for RTM classification."""

    def __init__(self):
        self.api_key = os.environ.get("LLM_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        self.env_base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.env_model = os.environ.get("LLM_MODEL", "google/gemini-3.1-flash-lite-preview")
        # Provider (model + base URL) — overridable by the super-admin in Settings
        self.base_url = self.env_base_url
        self.model = self.env_model
        # Behaviour — driven by the /rules AI section
        self.temperature = 0.3
        self.enrich_top_n = 15
        self.llm_enabled = True

    def _settings_path(self) -> str:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "data", "settings.json")

    def refresh_provider(self):
        """Re-read the model / base-URL overrides saved by the super-admin."""
        self.model = self.env_model
        self.base_url = self.env_base_url
        try:
            path = self._settings_path()
            if os.path.exists(path):
                with open(path) as f:
                    saved = json.load(f)
                if saved.get("llm_model"):
                    self.model = saved["llm_model"]
                if saved.get("llm_base_url"):
                    self.base_url = saved["llm_base_url"]
        except Exception:
            pass

    def apply_config(self, config: dict):
        """Apply the 'ai' section of the rule config (see backend/rule_defaults.py)."""
        ai = (config or {}).get("ai") or {}
        self.llm_enabled = bool(ai.get("llm_enabled", True))
        self.temperature = ai.get("temperature", 0.3)
        self.enrich_top_n = int(ai.get("enrich_top_n", 15) or 15)

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.llm_enabled

    def test_connection(self, model: str = None, base_url: str = None) -> dict:
        """Make a minimal LLM call to verify the model/provider works."""
        import time
        if not self.api_key:
            return {"ok": False, "message": "No API key configured — set OPENROUTER_API_KEY in .env"}
        use_model = model or self.model
        use_base = base_url or self.base_url
        t0 = time.time()
        try:
            resp = requests.post(
                f"{use_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": use_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=25,
            )
            latency = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                return {"ok": True, "message": "Connection successful", "model": use_model, "latency_ms": latency}
            detail = resp.text[:180].replace("\n", " ")
            return {"ok": False, "message": f"HTTP {resp.status_code}: {detail}", "model": use_model, "latency_ms": latency}
        except Exception as e:
            return {"ok": False, "message": str(e)[:180], "model": use_model}

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000,
                  usage_sink: list = None) -> Optional[str]:
        """Call the LLM. If usage_sink is a list, the response's usage object
        (token counts + real OpenRouter cost) is appended to it."""
        if not self.is_configured():
            return None
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": self.temperature,
                    "usage": {"include": True},   # ask OpenRouter for cost details
                },
                timeout=45,
            )
            resp.raise_for_status()
            data = resp.json()
            if usage_sink is not None and isinstance(data.get("usage"), dict):
                usage_sink.append(data["usage"])
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    # ================================================================
    # STEP-BY-STEP INSIGHT METHODS (called individually from pipeline)
    # ================================================================
    def generate_executive_summary(self, results_df: pd.DataFrame, usage_sink: list = None) -> str:
        """Step 10: Generate executive summary."""
        stats = self._build_stats(results_df)
        return self._call_llm(
            "You are a senior retail distribution analyst writing for a management team. Use markdown bullet points. Be data-driven and concise.",
            f"""Write an executive summary of this RTM outlet classification run:

{stats}

Structure:
- **Overview**: 1-2 sentences on overall portfolio health
- **Key Findings**: 3-4 bullets on revenue concentration, class distribution, notable patterns
- **Wholesaler Impact**: how wholesalers affect the classification
- **Risks**: 2-3 specific risk signals from the data
- **Recommended Actions**: 3-4 prioritized next steps with timelines""",
            max_tokens=800,
            usage_sink=usage_sink,
        ) or self._fallback_summary(results_df)

    def generate_recommendations(self, results_df: pd.DataFrame, usage_sink: list = None) -> Dict[str, str]:
        """Step 11: Generate class A/B/C recommendations."""
        class_data = {}
        for cls in ["Class A", "Class B", "Class C"]:
            cdf = results_df[results_df["Classification"].str.contains(cls.split()[-1], na=False)]
            rev = cdf["TotalSales_2Yr"].sum() if "TotalSales_2Yr" in cdf.columns else 0
            class_data[cls] = {"count": len(cdf), "revenue": f"${rev:,.0f}", "avg": f"${rev/max(len(cdf),1):,.0f}"}

        all_recs = self._call_llm(
            "You are a retail distribution consultant. Give specific, actionable strategies with KPIs. Use markdown.",
            f"""Provide recommendations for each outlet class. Context: Pareto 80/15/5 classification.

Data:
{json.dumps(class_data, indent=2)}

For EACH class (Class A, Class B, Class C) provide:
- 3-4 specific action items
- KPIs to track
- Timeline (30/60/90 day)

Use headers: ## Class A Recommendations, ## Class B Recommendations, ## Class C Recommendations""",
            max_tokens=1200,
            usage_sink=usage_sink,
        )

        recs = {}
        if all_recs:
            for cls_key, header in [("class_a_recs", "Class A"), ("class_b_recs", "Class B"), ("class_c_recs", "Class C")]:
                section = self._extract_section(all_recs, header)
                recs[cls_key] = section or self._fallback_recs(header)
        else:
            recs["class_a_recs"] = self._fallback_recs("Class A")
            recs["class_b_recs"] = self._fallback_recs("Class B")
            recs["class_c_recs"] = self._fallback_recs("Class C")
        return recs

    def generate_growth_analysis(self, results_df: pd.DataFrame, usage_sink: list = None) -> str:
        """Step 12: Generate growth trend analysis."""
        periods = {}
        for period, col in [("2Yr", "TotalSales_2Yr"), ("12M", "TotalSales_12M"),
                             ("6M", "TotalSales_6M"), ("3M", "TotalSales_3M")]:
            if col in results_df.columns:
                periods[period] = {"total": float(results_df[col].sum()), "avg": float(results_df[col].mean())}

        return self._call_llm(
            "You are a growth analyst. Be specific with numbers and percentages. Use markdown bullets.",
            f"""Analyze sales trends for {len(results_df)} outlets:

Period data: {json.dumps(periods, default=str)}

Provide:
- **Trend Direction**: growing, declining, or flat with % change
- **Period Comparison**: compare 3M vs 6M vs 12M momentum
- **Risk Signals**: outlets or segments showing decline
- **Growth Opportunities**: where to invest next
- **Seasonality**: any patterns visible""",
            max_tokens=600,
            usage_sink=usage_sink,
        ) or "Growth analysis not available."

    # Legacy method — calls step-by-step methods
    def generate_all_insights(self, results_df: pd.DataFrame) -> Dict[str, str]:
        """Calls each insight step individually. Used as batch fallback."""
        insights = {}
        insights["executive_summary"] = self.generate_executive_summary(results_df)
        recs = self.generate_recommendations(results_df)
        insights.update(recs)
        insights["growth_analysis"] = self.generate_growth_analysis(results_df)
        return insights

    # ================================================================
    # PER-OUTLET AI COLUMNS: Added to DataFrame for Excel export
    # ================================================================
    def enrich_outlets(self, results_df: pd.DataFrame, config: dict = None, usage_sink: list = None) -> pd.DataFrame:
        """Add AI-computed columns to each outlet row. Rule-based (free) + LLM for top outlets.

        config: optional rule parameters (see backend/rule_defaults.py) for the
                growth-signal and risk-scoring thresholds.
        """
        df = results_df.copy()
        config = config or {}
        growth_cfg = config.get("growth") or {}
        risk_cfg = config.get("risk") or {}

        grow_mult = 1 + growth_cfg.get("growing_pct", 10) / 100
        decl_mult = 1 - growth_cfg.get("declining_pct", 10) / 100

        risk_med_days = risk_cfg.get("freq_medium_days", 30)
        risk_high_days = risk_cfg.get("freq_high_days", 60)
        risk_low_purchase = risk_cfg.get("low_purchase_days", 5)
        signals_high = risk_cfg.get("signals_for_high", 3)
        signals_medium = risk_cfg.get("signals_for_medium", 1)

        # ── Rule-based columns (free, computed from data) ──

        # 1. Growth Signal: compare recent vs historical
        if "TotalSales_12M" in df.columns and "TotalSales_6M" in df.columns:
            half_12m = df["TotalSales_12M"] / 2  # normalized to 6M equivalent
            df["AI_Growth_Signal"] = np.where(
                df["TotalSales_6M"] > half_12m * grow_mult, "Growing",
                np.where(df["TotalSales_6M"] < half_12m * decl_mult, "Declining", "Stable")
            )
        elif "TotalSales_2Yr" in df.columns:
            df["AI_Growth_Signal"] = "N/A"

        # 2. Risk Level
        def calc_risk(row):
            signals = 0
            # Declining sales
            if row.get("AI_Growth_Signal") == "Declining":
                signals += 2
            # Low frequency (buys rarely)
            freq = row.get("Frequency_2Yr", 0)
            if freq and freq > risk_med_days:
                signals += 1
            if freq and freq > risk_high_days:
                signals += 1
            # Low purchase days
            days = row.get("PurchaseDays_2Yr", 0)
            if days and days < risk_low_purchase:
                signals += 1
            if signals >= signals_high:
                return "High"
            elif signals >= signals_medium:
                return "Medium"
            return "Low"

        df["AI_Risk_Level"] = df.apply(calc_risk, axis=1)

        # 3. Action Item per outlet
        def calc_action(row):
            cls = str(row.get("Classification", ""))
            growth = row.get("AI_Growth_Signal", "")
            risk = row.get("AI_Risk_Level", "")
            ws = row.get("Is_Wholesaler", False)

            if ws:
                return "Maintain bulk pricing; monitor carton volumes monthly"
            if "Class A" in cls:
                if growth == "Declining":
                    return "URGENT: Schedule account review; investigate sales drop"
                if risk == "High":
                    return "Retention risk - assign senior account manager"
                return "Maintain priority service; quarterly business review"
            elif "Class B" in cls:
                if growth == "Growing":
                    return "High potential - increase visit frequency; upsell campaign"
                if growth == "Declining":
                    return "Monitor closely; run targeted promotion"
                return "Growth incentive program; monthly check-in"
            else:  # Class C
                if growth == "Growing":
                    return "Emerging outlet - increase engagement; potential upgrade"
                if risk == "High":
                    return "Review cost-to-serve; consider consolidation"
                return "Standard service; quarterly viability review"

        df["AI_Action"] = df.apply(calc_action, axis=1)

        # 4. Visit Priority (1-5 scale)
        def calc_priority(row):
            cls = str(row.get("Classification", ""))
            risk = row.get("AI_Risk_Level", "")
            growth = row.get("AI_Growth_Signal", "")
            if "Class A" in cls and risk in ("High", "Medium"):
                return 1  # highest
            if "Class A" in cls:
                return 2
            if "Class B" in cls and growth == "Growing":
                return 2
            if "Class B" in cls:
                return 3
            if "Class C" in cls and growth == "Growing":
                return 3
            return 4

        df["AI_Visit_Priority"] = df.apply(calc_priority, axis=1)

        # ── LLM-enriched: batch top 15 outlets for personalized insights ──
        if self.is_configured() and "Cus.Name" in df.columns and "TotalSales_2Yr" in df.columns:
            top_n = max(1, self.enrich_top_n)
            top_outlets = df.nlargest(top_n, "TotalSales_2Yr")
            outlet_data = []
            for _, r in top_outlets.iterrows():
                outlet_data.append({
                    "code": r.get("Cus.Code", ""),
                    "name": r.get("Cus.Name", ""),
                    "class": r.get("Classification", ""),
                    "sales_2yr": float(r.get("TotalSales_2Yr", 0)),
                    "sales_6m": float(r.get("TotalSales_6M", 0)) if "TotalSales_6M" in df.columns else None,
                    "growth": r.get("AI_Growth_Signal", ""),
                    "frequency": float(r.get("Frequency_2Yr", 0)) if "Frequency_2Yr" in df.columns else None,
                    "wholesaler": bool(r.get("Is_Wholesaler", False)),
                })

            batch_result = self._call_llm(
                "You are a sales analyst. For each outlet, write ONE specific sentence about their performance and what to do next. Return as numbered list matching the order given.",
                f"Write a 1-sentence personalized insight for each of these top {top_n} outlets:\n\n{json.dumps(outlet_data, default=str, indent=1)}",
                max_tokens=1000,
                usage_sink=usage_sink,
            )

            if batch_result:
                lines = [l.strip() for l in batch_result.strip().split("\n") if l.strip()]
                # Clean up numbering
                clean_lines = []
                for l in lines:
                    for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "11.", "12.", "13.", "14.", "15.", "-", "*"]:
                        if l.startswith(prefix):
                            l = l[len(prefix):].strip()
                            break
                    if l:
                        clean_lines.append(l)

                # Map back to dataframe
                df["AI_Insight"] = ""
                for i, (idx, _) in enumerate(top_outlets.iterrows()):
                    if i < len(clean_lines):
                        df.loc[idx, "AI_Insight"] = clean_lines[i]
            else:
                df["AI_Insight"] = ""
        else:
            df["AI_Insight"] = ""

        return df

    # ================================================================
    # HELPERS
    # ================================================================

    def _build_stats(self, df) -> str:
        lines = [f"Total outlets: {len(df)}"]
        if "TotalSales_2Yr" in df.columns:
            lines.append(f"Total 2Yr revenue: ${df['TotalSales_2Yr'].sum():,.0f}")
            lines.append(f"Avg per outlet: ${df['TotalSales_2Yr'].mean():,.0f}")
            lines.append(f"Max: ${df['TotalSales_2Yr'].max():,.0f}, Min: ${df['TotalSales_2Yr'].min():,.0f}")
        if "Classification" in df.columns:
            for cls, count in df["Classification"].value_counts().items():
                cls_rev = df[df["Classification"] == cls]["TotalSales_2Yr"].sum() if "TotalSales_2Yr" in df.columns else 0
                lines.append(f"{cls}: {count} outlets (${cls_rev:,.0f})")
        if "Is_Wholesaler" in df.columns:
            lines.append(f"Wholesalers: {int(df['Is_Wholesaler'].sum())}")
        if "Frequency_2Yr" in df.columns:
            lines.append(f"Avg frequency: every {df['Frequency_2Yr'].mean():.1f} days")
        if "Cus.Name" in df.columns and "TotalSales_2Yr" in df.columns:
            top5 = df.nlargest(5, "TotalSales_2Yr")
            lines.append("Top 5:")
            for _, r in top5.iterrows():
                lines.append(f"  {r['Cus.Name']}: ${r['TotalSales_2Yr']:,.0f} ({r['Classification']})")
        return "\n".join(lines)

    def _extract_section(self, text: str, header: str) -> str:
        """Extract a section from markdown text by header."""
        lines = text.split("\n")
        capture = False
        result = []
        for line in lines:
            if header.lower() in line.lower() and "#" in line:
                capture = True
                continue
            elif capture and line.strip().startswith("##"):
                break
            elif capture:
                result.append(line)
        return "\n".join(result).strip() if result else None

    def _fallback_summary(self, df) -> str:
        total = len(df)
        rev = df["TotalSales_2Yr"].sum() if "TotalSales_2Yr" in df.columns else 0
        counts = df["Classification"].value_counts().to_dict() if "Classification" in df.columns else {}
        lines = [f"- **{total:,} outlets** classified | **${rev:,.0f}** total 2-year revenue"]
        for cls, cnt in counts.items():
            lines.append(f"- {cls}: {cnt} outlets ({cnt/total*100:.0f}%)")
        return "\n".join(lines)

    def _fallback_recs(self, classification: str) -> str:
        recs = {
            "Class A": "- Assign dedicated account managers\n- Priority delivery and service\n- Exclusive promotions and early product access\n- Quarterly business reviews",
            "Class B": "- Growth incentive programs\n- Training and merchandising support\n- Upselling campaigns\n- Monthly performance monitoring",
            "Class C": "- Review cost-to-serve ratio\n- Consider consolidation\n- Standard service level\n- Quarterly viability assessment",
        }
        return recs.get(classification, "- Standard monitoring")


# Singleton
_ai_service = None

def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    _ai_service.refresh_provider()  # pick up any saved model/provider overrides
    return _ai_service


def summarize_usage(usage_sink: list) -> dict:
    """Sum a list of OpenRouter usage objects (token counts + real cost)."""
    prompt = completion = total = 0
    cost = 0.0
    for u in (usage_sink or []):
        prompt += int(u.get("prompt_tokens", 0) or 0)
        completion += int(u.get("completion_tokens", 0) or 0)
        total += int(u.get("total_tokens", 0) or 0)
        try:
            cost += float(u.get("cost", 0) or 0)
        except Exception:
            pass
    if not total:
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cost": round(cost, 6),
        "calls": len(usage_sink or []),
    }
