from dataclasses import dataclass
from enum import Enum
from src.recovery.failure_classifier import FailurePacket, FailureType
from src.tools.order_service import cursor, conn


class RecoveryAction(Enum):
    ROLLBACK = "rollback"
    TERMINATE = "terminate"
    RETRY = "retry"
    RENTRY = "retry"


@dataclass
class RecoveryResult:
    action: RecoveryAction
    success: bool
    detail: str


@dataclass
class BudgetTracker:
    max_retries: int = 2
    max_tool_calls: int = 5
    retry_count: int = 0
    tool_call_count: int = 0

    def can_retry(self) -> bool:
        return (
            self.retry_count < self.max_retries
            and self.tool_call_count < self.max_tool_calls
        )

    def retries_remaining(self, max_retries: int | None = None) -> int:
        effective_max = self.max_retries
        if max_retries is not None:
            effective_max = min(effective_max, max_retries)
        return max(0, effective_max - self.retry_count)

    def record_retry(self):
        self.retry_count += 1

    def consume_retry(self):
        self.record_retry()

    def record_tool_call(self):
        self.tool_call_count += 1

    def budget_exhausted_reason(self) -> str:
        if self.retry_count >= self.max_retries:
            return f"max retries reached({self.max_retries})"
        if self.tool_call_count >= self.max_tool_calls:
            return f"max tool calls reached ({self.max_tool_calls})"
        return ""


def _rollback_order(order_id: int) -> bool:
    try:
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))  # type: ignore
        conn.commit()
        return cursor.rowcount > 0  # type: ignore
    except Exception:
        return False


def recover(
    failure: FailurePacket, diff=None, budget: BudgetTracker | None = None
) -> RecoveryResult:

    # Budget check: if exhausted, force terminate
    if budget and not budget.can_retry():
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=f"Budget exhausted: {budget.budget_exhausted_reason()}",
        )

    # Gate Failure
    if failure.failure_type == FailureType.GATE_SCHEMA_BLOCKED:
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=f"Schema violation, no auto-fix in v0: {failure.reason}",
        )

    if failure.failure_type == FailureType.GATE_POLICY_BLOCKED:
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=f"Policy violation, cannot bypass: {failure.reason}",
        )

    if failure.failure_type == FailureType.GATE_DEPENDENCY_BLOCKED:
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=f"Dependency violation, prerequisite step not executed: {failure.reason}",
        )

    # Verifier Failure
    if failure.failure_type == FailureType.FALSE_SUCCESS:
        # Rollback to delete the corrupted order
        if diff and diff.new_order:
            order_id = diff.new_order["id"]
            roll_back = _rollback_order(order_id)
            if roll_back:
                return RecoveryResult(
                    action=RecoveryAction.ROLLBACK,
                    success=True,
                    detail=f"Rolled back order {order_id}: {failure.reason}",
                )
            else:
                return RecoveryResult(
                    action=RecoveryAction.ROLLBACK,
                    success=False,
                    detail=f"Rollback failed for order {order_id}: {failure.reason}",
                )

        return RecoveryResult(
            action=RecoveryAction.ROLLBACK,
            success=True,
            detail=f"FALSE_SUCCESS detected: environment state already clean (no persisted record found). Reason: {failure.reason}",
        )

    if failure.failure_type == FailureType.REFERENCE_DOI_FAILED:
        max_retries_for_failure = 2
        if (
            budget
            and budget.can_retry()
            and budget.retries_remaining(max_retries_for_failure) > 0
        ):
            budget.consume_retry()
            return RecoveryResult(
                action=RecoveryAction.RETRY,
                success=True,
                detail=(
                    "DOI verification failed for this reference. "
                    "The DOI does not exist or does not match the paper metadata. "
                    "Flag this reference as unverifiable and proceed to the next reference."
                ),
            )
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=(
                "Max retries reached. This reference cannot be verified. "
                "Mark doi_status as unverifiable and continue."
            ),
        )

    if failure.failure_type == FailureType.VERIFY_FAIL:
        if budget and budget.can_retry():
            budget.record_retry()
            return RecoveryResult(
                action=RecoveryAction.RETRY,
                success=True,
                detail=f"Verification failed, retrying ({budget.retry_count}/{budget.max_retries}): {failure.reason}",
            )
        return RecoveryResult(
            action=RecoveryAction.TERMINATE,
            success=False,
            detail=f"Verification failed, no retries left: {failure.reason}",
        )

    # Fallback
    return RecoveryResult(
        action=RecoveryAction.TERMINATE,
        success=False,
        detail=f"Unknown failure type: {failure.failure_type}",
    )
