from dotenv import load_dotenv
from mistralai.models import UserMessage, ToolMessage
from mistralai import Mistral
import os
from typing import Any
from src.tools.order_tools import tools, create_order, get_order_status
import json
from src.gate.shcema_validator import validate as gate_validate
from src.verifier.state_tracker import take_snapshot, compute_diff
from src.verifier.verifier import verify
from src.tools.order_tools import cursor
from src.verifier.verifier import verify, VerifierResult
from src.recovery.failure_classifier import (
    classify_gate_failure,
    classify_verifier_failure,
)
from src.recovery.recovery_controller import recover, BudgetTracker, RecoveryAction


def run_agent(msg: str):

    print(f"\n{'='*50}")
    print(f"[INPUT]    {msg}")

    test_result = {
        "input": msg,
        "tool_called": False,
        "args_passed": None,
        "gate_blocked": False,
        "gate_reason": None,
        "final_answer": None,
    }

    # Record successfully excuted tools
    executed_tools: list[str] = []

    # Create bugdet tracker per task
    budget = BudgetTracker()

    # Initial Mistral.ai Client
    load_dotenv()
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    messages: list[Any] = [UserMessage(content=msg)]

    # First request
    response = client.chat.complete(
        model="mistral-small-latest",
        messages=messages,
        tools=tools, # type: ignore
        tool_choice="auto",  # type: ignore
    )

    # Second request, add data in dataset
    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)  # type: ignore
            gate_result = gate_validate(func_name, func_args, executed_tools)

            if not gate_result.allowed:
                print(f"[GATE]    BLOCKED - {gate_result.reason}")
                # Classify and recover
                failure = classify_gate_failure(gate_result, func_name)
                recovery_result = recover(failure, budget=budget)
                print(
                    f"[RECOVERY]    {recovery_result.action.value} — {recovery_result.detail}"
                )
                test_result["recovery_action"] = recovery_result.action.value
                test_result["recovery_detail"] = recovery_result.detail

                test_result["tool_called"] = True
                test_result["gate_blocked"] = True
                test_result["gate_reason"] = gate_result.reason
                test_result["args_passed"] = func_args
                # return the reason to LLM
                messages.append(response.choices[0].message)
                messages.append(
                    ToolMessage(
                        tool_call_id=tool_call.id,
                        content=f"Gate denied: {gate_result.reason}",
                    )
                )
                continue

            print(f"[GATE]     PASSED — args={func_args}")

            # Track tool call in budget
            budget.record_tool_call()

            # snapshot before status
            snapshot_before = take_snapshot(cursor)

            # Gate passthrough
            if func_name == "create_order":
                result = create_order(**func_args)
            elif func_name == "get_order_status":
                result = get_order_status(**func_args)

            print(f"[EXECUTOR]    {func_name}({func_args}) => {result}")  # type: ignore
            executed_tools.append(func_name)

            # snapshot after status
            snapshot_after = take_snapshot(cursor)
            diff = compute_diff(snapshot_before, snapshot_after)

            if func_name == "create_order":
                verifier_result = verify(func_name, func_args, diff)

                # Independent detection intent - parameter inconsistency
                if verifier_result.passed and func_name == "create_order":
                    negative_signals = ["-", "negative", "minus", "负"]
                    user_intended_negative = any(
                        s in msg.lower() for s in negative_signals
                    )
                    if (
                        user_intended_negative
                        and diff.new_order
                        and diff.new_order["amount"] > 0
                    ):
                        verifier_result = VerifierResult(
                            passed=False,
                            verdict="FALSE_SUCCESS",
                            evidence=f"User input suggests negative amount, but DB recorded amount={diff.new_order['amount']}. Silent sign conversion detected.",
                        )

                print(
                    f"[VERIFIER]    {verifier_result.verdict} — {verifier_result.evidence}"
                )
                test_result["verifier_verdict"] = verifier_result.verdict

                # If verifier failed, classify and recover
                if not verifier_result.passed:
                    failure = classify_verifier_failure(verifier_result)
                    recovery_result = recover(failure, diff=diff, budget=budget)
                    print(
                        f"[RECOVERY]    {recovery_result.action.value} — {recovery_result.detail}"
                    )
                    test_result["recovery_action"] = recovery_result.action.value
                    test_result["recovery_detail"] = recovery_result.detail
                    # Overwrite tool result so LLM sees the recovery outcome
                    result = {
                        "error": recovery_result.detail,
                        "action_taken": recovery_result.action.value,
                        "system_note": "The corrupted record has been rolled back and deleted from the database. No order exists from this operation.",
                    }

            test_result["tool_called"] = True
            test_result["args_passed"] = func_args
            messages.append(response.choices[0].message)
            messages.append(
                ToolMessage(
                    tool_call_id=tool_call.id,
                    content=json.dumps(result),  # type: ignore
                )
            )

        final = client.chat.complete(
            model="mistral-small-latest",
            messages=messages,  # type: ignore
        )
        test_result["final_answer"] = final.choices[0].message.content
        print(f"[ANSWER]    {test_result['final_answer']}")
        return test_result
    else:
        test_result["final_answer"] = response.choices[0].message.content
        print(f"[GATE]    NOT TRIGGERED — model refused to call tool")
        print(f"[ANSWER]    {test_result['final_answer']}")
        return test_result
