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
        self.base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.environ.get("LLM_MODEL", "google/gemini-3.1-flash-lite-preview")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> Optional[str]:
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
                    "temperature": 0.3,
                },
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            return None

    # ================================================================
    # MAIN METHOD: Generate all insights in one go during pipeline
    # ================================================================
    def generate_all_insights(self, results_df: pd.DataFrame) -> Dict[str, str]:
        """
        Auto-generate all insights. Called once after classification.
        Returns dict with keys: executive_summary, class_a_recs, class_b_recs, class_c_recs, growth_analysis
        """
        stats = self._build_stats(results_df)
        insights = {}

        # 1. Executive Summary
        insights["executive_summary"] = self._call_llm(
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
        ) or self._fallback_summary(results_df)

        # 2. Class Recommendations (one call for all classes)
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
        )

        if all_recs:
            # Split into sections
            for cls_key, header in [("class_a_recs", "Class A"), ("class_b_recs", "Class B"), ("class_c_recs", "Class C")]:
                section = self._extract_section(all_recs, header)
                insights[cls_key] = section or self._fallback_recs(header)
        else:
            insights["class_a_recs"] = self._fallback_recs("Class A")
            insights["class_b_recs"] = self._fallback_recs("Class B")
            insights["class_c_recs"] = self._fallback_recs("Class C")

        # 3. Growth Analysis
        periods = {}
        for period, col in [("2Yr", "TotalSales_2Yr"), ("12M", "TotalSales_12M"),
                             ("6M", "TotalSales_6M"), ("3M", "TotalSales_3M")]:
            if col in results_df.columns:
                periods[period] = {"total": float(results_df[col].sum()), "avg": float(results_df[col].mean())}

        insights["growth_analysis"] = self._call_llm(
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
        ) or "Growth analysis not available."

        return insights

    # ================================================================
    # PER-OUTLET AI COLUMNS: Added to DataFrame for Excel export
    # ================================================================
    def enrich_outlets(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Add AI-computed columns to each outlet row. Rule-based (free) + LLM for top outlets."""
        df = results_df.copy()

        # ── Rule-based columns (free, computed from data) ──

        # 1. Growth Signal: compare recent vs historical
        if "TotalSales_12M" in df.columns and "TotalSales_6M" in df.columns:
            half_12m = df["TotalSales_12M"] / 2  # normalized to 6M equivalent
            df["AI_Growth_Signal"] = np.where(
                df["TotalSales_6M"] > half_12m * 1.1, "Growing",
                np.where(df["TotalSales_6M"] < half_12m * 0.9, "Declining", "Stable")
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
            if freq and freq > 30:
                signals += 1
            if freq and freq > 60:
                signals += 1
            # Low purchase days
            days = row.get("PurchaseDays_2Yr", 0)
            if days and days < 5:
                signals += 1
            if signals >= 3:
                return "High"
            elif signals >= 1:
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
            top15 = df.nlargest(15, "TotalSales_2Yr")
            outlet_data = []
            for _, r in top15.iterrows():
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
                f"Write a 1-sentence personalized insight for each of these top 15 outlets:\n\n{json.dumps(outlet_data, default=str, indent=1)}",
                max_tokens=1000,
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
                for i, (idx, _) in enumerate(top15.iterrows()):
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
    return _ai_service
