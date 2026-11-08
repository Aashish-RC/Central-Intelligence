"""
Pheonix Renewal Engine
Calculates upcoming billing renewals, countdowns, and payment rollover schedules.
"""

from datetime import date, timedelta
from typing import List, Optional
from ..models import SubscriptionPlan, ProviderRenewal


class RenewalEngine:
    """Calculates subscription renewal dates and countdowns."""

    @staticmethod
    def calculate_renewal(plan: SubscriptionPlan, reference_date: Optional[date] = None) -> ProviderRenewal:
        """
        Determines the next renewal date and days remaining relative to reference_date.
        """
        ref = reference_date or date.today()
        day = plan.renewal_day_of_month

        # Clamp day if target month has fewer days (e.g. Feb 30 -> Feb 28)
        year = ref.year
        month = ref.month

        if ref.day < day:
            target_month = month
            target_year = year
        else:
            if month == 12:
                target_month = 1
                target_year = year + 1
            else:
                target_month = month + 1
                target_year = year

        # Compute valid date handling month lengths
        max_days = 31
        if target_month in [4, 6, 9, 11]:
            max_days = 30
        elif target_month == 2:
            is_leap = (target_year % 4 == 0 and target_year % 100 != 0) or (target_year % 400 == 0)
            max_days = 29 if is_leap else 28

        safe_day = min(day, max_days)
        next_date = date(target_year, target_month, safe_day)
        days_remaining = (next_date - ref).days

        status = "active"
        if days_remaining <= 3:
            status = "due_soon"

        return ProviderRenewal(
            provider=plan.provider,
            plan_name=plan.name,
            next_renewal_date=next_date.isoformat(),
            days_remaining=days_remaining,
            estimated_renewal_cost_usd=plan.monthly_cost_usd,
            status=status
        )

    @classmethod
    def list_renewals(cls, plans: List[SubscriptionPlan], reference_date: Optional[date] = None) -> List[ProviderRenewal]:
        """Calculates and sorts all upcoming renewals by urgency (days remaining)."""
        renewals = [cls.calculate_renewal(p, reference_date=reference_date) for p in plans]
        renewals.sort(key=lambda r: r.days_remaining)
        return renewals
