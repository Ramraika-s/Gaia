"""
sim_core/society/economy.py
Closed-loop double-entry credit transfers, World Bank currency issuer,
and loan lifecycle management.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 1.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sim_core.schemas import AgentRecord as AgentState
from sim_core.schemas import BankLoanRecord


class EconomyError(Exception):
    """Raised when an economic transfer or bank operation fails."""

    pass


class WorldBank:
    """
    Sole currency issuer in Gaia. Holds reserve credits, issues loans,
    and tracks credit scores and default seizures.
    """

    def __init__(self, initial_reserve: float = 1_000_000.0):
        self.reserve_credits: float = initial_reserve
        self.loans: dict[str, BankLoanRecord] = {}
        self.defaulted_cases: list[dict[str, Any]] = []

    @property
    def credits(self) -> float:
        return self.reserve_credits

    @credits.setter
    def credits(self, value: float) -> None:
        self.reserve_credits = value

    def issue_currency(self, recipient: AgentState | Any, amount: float) -> bool:
        """
        Transfers initial endowment from Bank reserve to recipient.
        Strict double-entry: debits bank reserve, credits recipient.
        """
        if amount <= 0:
            return False
        if self.reserve_credits < amount:
            return False
        self.reserve_credits -= amount
        recipient.credits += amount
        return True

    def transfer_credits(
        self,
        sender: AgentState | Any,
        receiver: AgentState | Any,
        amount: float,
        memo: str = "TRANSFER",
    ) -> tuple[bool, str]:
        """
        Strict closed-loop double-entry credit transfer.
        Never mints or destroys currency.
        Fails if sender.credits < amount.
        """
        if amount <= 0:
            return False, "INVALID_AMOUNT: transfer amount must be > 0"

        if sender.credits < amount:
            return False, f"INSUFFICIENT_FUNDS: sender has {sender.credits:.2f}, needs {amount:.2f}"

        sender.credits -= amount
        receiver.credits += amount
        return True, "SUCCESS"

    def issue_loan(
        self,
        borrower: AgentState | Any,
        principal: float,
        holder_type: Literal["AGENT", "SETTLEMENT", "NATION", "CHURCH"],
        current_tick: int,
        interest_rate: float = 0.02,
    ) -> tuple[bool, str, BankLoanRecord | None]:
        """
        Issues a loan from Bank reserve to borrower.
        Requires credit_score >= 580 for AGENT.
        """
        if principal <= 0:
            return False, "INVALID_PRINCIPAL", None

        if self.reserve_credits < principal:
            return False, "INSUFFICIENT_BANK_RESERVE", None

        # Qualification check
        if holder_type == "AGENT":
            if getattr(borrower, "stage", "ADULT") != "ADULT":
                return False, "DISQUALIFIED: only adults may borrow", None
            score = getattr(borrower, "credit_score", 650.0)
            if score < 580.0:
                return False, f"CREDIT_TOO_LOW: score {score} < 580", None

        # Transfer principal
        self.reserve_credits -= principal
        borrower.credits += principal

        total_due = principal * (1.0 + interest_rate)
        loan_id = f"loan_{uuid.uuid4().hex[:8]}"
        holder_id = getattr(borrower, "agent_id", None) or str(
            getattr(borrower, "settlement_id", loan_id)
        )
        loan = BankLoanRecord(
            loan_id=loan_id,
            holder_id=holder_id,
            holder_type=holder_type,
            principal=principal,
            remaining_balance=total_due,
            interest_rate=interest_rate,
            missed_windows=0,
            status="GOOD",
            issued_tick=current_tick,
        )
        self.loans[loan_id] = loan
        return True, "LOAN_ISSUED", loan

    def process_loan_repayment(
        self,
        borrower: AgentState | Any,
        loan_id: str,
        installment: float,
    ) -> tuple[bool, str]:
        """Processes partial or full repayment of a loan."""
        if loan_id not in self.loans:
            return False, "LOAN_NOT_FOUND"

        loan = self.loans[loan_id]
        if loan.status in ("PAID", "DEFAULTED"):
            return False, f"LOAN_{loan.status}"

        payment = min(installment, loan.remaining_balance)
        if borrower.credits < payment:
            return False, "INSUFFICIENT_FUNDS_FOR_REPAYMENT"

        # Debit borrower, credit World Bank reserve
        borrower.credits -= payment
        self.reserve_credits += payment
        loan.remaining_balance -= payment

        if hasattr(borrower, "credit_score"):
            borrower.credit_score = min(850.0, borrower.credit_score + 5.0)

        if loan.remaining_balance <= 0.001:
            loan.remaining_balance = 0.0
            loan.status = "PAID"
            return True, "LOAN_PAID_IN_FULL"

        loan.missed_windows = 0
        loan.status = "GOOD"
        return True, "REPAYMENT_ACCEPTED"

    def evaluate_missed_window(
        self,
        borrower: AgentState | Any,
        loan_id: str,
        current_tick: int,
    ) -> tuple[str, dict[str, Any] | None]:
        """
        Called when a scheduled repayment window passes without payment.
        At 3 misses, marks DEFAULTED, slashes credit score, and creates judiciary incident.
        """
        if loan_id not in self.loans:
            return "LOAN_NOT_FOUND", None

        loan = self.loans[loan_id]
        if loan.status in ("PAID", "DEFAULTED"):
            return loan.status, None

        loan.missed_windows += 1
        if hasattr(borrower, "credit_score"):
            borrower.credit_score = max(300.0, borrower.credit_score - 25.0)

        if loan.missed_windows >= 3:
            loan.status = "DEFAULTED"
            if hasattr(borrower, "credit_score"):
                borrower.credit_score = max(300.0, borrower.credit_score - 100.0)

            case = {
                "case_id": f"case_debt_{uuid.uuid4().hex[:8]}",
                "accused_id": getattr(borrower, "agent_id", loan.holder_id),
                "offense_type": "DEBT_DEFAULT",
                "defaulted_amount": loan.remaining_balance,
                "tick": current_tick,
            }
            self.defaulted_cases.append(case)
            return "DEFAULTED", case

        loan.status = "DELINQUENT"
        return "DELINQUENT", None

    @staticmethod
    def calculate_total_circulation(
        agents: list[AgentState],
        settlement_treasuries: list[float] | None = None,
        church_treasuries: list[float] | None = None,
    ) -> float:
        """Computes circulating money supply M."""
        total = sum(a.credits for a in agents if a.alive)
        if settlement_treasuries:
            total += sum(settlement_treasuries)
        if church_treasuries:
            total += sum(church_treasuries)
        return total
