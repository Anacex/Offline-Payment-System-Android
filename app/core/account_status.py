"""Account suspension / fraud-review gates for API access."""

from fastapi import HTTPException, status

from app.models.user import User


def raise_if_account_blocked(user: User) -> None:
    """Reject API use when the account is suspended pending manual review."""
    if not getattr(user, "account_blocked", False):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "ACCOUNT_BLOCKED",
            "message": (
                "Your account is suspended pending manual review due to a security check. "
                "If you believe this is a mistake, contact support."
            ),
            "reason": user.account_blocked_reason,
            "fraud_review_pending": bool(getattr(user, "fraud_review_pending", False)),
        },
    )
