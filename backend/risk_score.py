"""
risk_score.py - Rule-Based Quantitative Risk Scoring Engine (0-100)
Configuration Drift Validator (College Project Phase 2)

Calculates a deterministic risk score (0 to 100) and risk tier based on:
- Target Environment (Production vs Staging vs Development)
- Configuration Category (Database, Secrets, Infrastructure, Runtime, Application)
- Severity of Detected Discrepancies
- Out-of-band Runtime Drift

NOTE: This is a transparent, prototype rule-based scoring algorithm designed for
academic demonstration and DevOps pre-flight risk assessment, not a commercial ML model.
"""

from typing import List, Dict, Any, Optional
from backend.schemas import SeverityEnum, DriftDiscrepancy

def calculate_risk_score(
    environment: str,
    discrepancies: Optional[List[DriftDiscrepancy]] = None,
    changed_keys: Optional[Dict[str, Any]] = None,
    has_runtime_drift: bool = False
) -> Dict[str, Any]:
    """
    Computes an explainable 0-100 risk score and tier.
    Returns:
        {
            "score": int,
            "level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
            "breakdown": List[str],
            "explanation": str,
            "is_blocked": bool
        }
    """
    env_lower = environment.lower()
    is_prod = env_lower == "production"
    is_stage = env_lower == "staging"

    score = 0
    breakdown: List[str] = []

    # 1. Base Environment Factor
    if is_prod:
        score += 25
        breakdown.append("Production environment targeted (+25 base impact)")
    elif is_stage:
        score += 10
        breakdown.append("Staging environment targeted (+10 base impact)")
    else:
        score += 5
        breakdown.append("Development environment targeted (+5 base impact)")

    discrepancies = discrepancies or []

    # 2. Analyze Discrepancies
    crit_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.CRITICAL)
    high_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.HIGH)
    med_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.MEDIUM)
    low_count = sum(1 for d in discrepancies if d.severity == SeverityEnum.LOW)

    if crit_count > 0:
        added = min(40, crit_count * 30)
        score += added
        breakdown.append(f"{crit_count} Critical severity issue(s) detected (+{added})")

    if high_count > 0:
        added = min(25, high_count * 15)
        score += added
        breakdown.append(f"{high_count} High severity issue(s) detected (+{added})")

    if med_count > 0:
        added = min(15, med_count * 7)
        score += added
        breakdown.append(f"{med_count} Medium severity issue(s) detected (+{added})")

    if low_count > 0:
        added = min(5, low_count * 2)
        score += added
        breakdown.append(f"{low_count} Low severity issue(s) detected (+{added})")

    # 3. Domain-Specific Penalties
    for d in discrepancies:
        key_upper = d.item_key.upper()
        # Database danger in prod
        if is_prod and "DATABASE" in key_upper and any(bad in str(d.actual_val).lower() for bad in ["dev", "localhost", "127.0.0.1", "staging"]):
            score += 15
            breakdown.append(f"Production database points to non-production target '{d.actual_val}' (+15)")
            break

    for d in discrepancies:
        key_upper = d.item_key.upper()
        if is_prod and key_upper == "DEBUG" and "true" in str(d.actual_val).lower():
            score += 15
            breakdown.append("Debug mode enabled in live production (+15)")
            break

    # Missing secrets
    secret_issues = [d for d in discrepancies if d.category == "secret"]
    if is_prod and secret_issues:
        score += 10
        breakdown.append("Production secret store discrepancy (+10)")

    # Runtime Drift
    if has_runtime_drift or any(d.category == "runtime" for d in discrepancies):
        score += 15
        breakdown.append("Live container state drifted from approved baseline (+15)")

    # 4. Changed Keys Context (if analyzing a pending commit or change request)
    if changed_keys:
        for k, v in changed_keys.items():
            k_upper = k.upper()
            if is_prod and "DATABASE" in k_upper and any(bad in str(v).lower() for bad in ["dev", "localhost", "staging"]):
                score += 25
                breakdown.append(f"Proposed commit changes {k} to test host '{v}' (+25)")
            if is_prod and k_upper == "DEBUG" and str(v).lower() in ["true", "1", "yes"]:
                score += 20
                breakdown.append(f"Proposed commit enables DEBUG in production (+20)")

    # Normalize to 0-100 range
    final_score = max(0, min(100, score))

    # Tiers
    if final_score >= 75 or crit_count > 0:
        level = "CRITICAL"
        is_blocked = True
    elif final_score >= 50 or high_count > 0:
        level = "HIGH"
        is_blocked = False
    elif final_score >= 25:
        level = "MEDIUM"
        is_blocked = False
    else:
        level = "LOW"
        is_blocked = False

    # Explanation summary
    if breakdown:
        explanation = " + ".join([b.split(" (")[0] for b in breakdown[:3]]) + f" = Risk Score {final_score}/100 ({level} Risk)"
    else:
        explanation = f"Clean configuration baseline. Risk Score {final_score}/100 ({level} Risk)"

    return {
        "score": final_score,
        "level": level,
        "breakdown": breakdown,
        "explanation": explanation,
        "is_blocked": is_blocked,
        "critical_issues": crit_count,
        "high_issues": high_count
    }
