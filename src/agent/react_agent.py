from dotenv import load_dotenv
from mistralai.models import UserMessage, ToolMessage
from mistralai import Mistral
import os
from typing import Any
from src.tools.order_tools import tools, create_order, get_order_status
import json
from src.gate.shcema_validator import validate as gate_validate


def run_agent(msg: str):

    test_result = {
        "input": msg,
        "tool_called": False,
        "args_passed": None,
        "gate_blocked": False,
        "gate_reason": None,
        "final_answer": None,
    }

    # Initial Mistral Client
    load_dotenv()
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    messages: list[Any] = [UserMessage(content=msg)]

    # First request
    response = client.chat.complete(
        model="mistral-small-latest", messages=messages, tools=tools, tool_choice="auto"  # type: ignore
    )
    print(response)

    # Second request, add data in dataset
    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)  # type: ignore
            gate_result = gate_validate(func_name, func_args)
            print(f"raw output: {str(func_args)}")

            if not gate_result.allowed:
                print(f"Gate Interception: {gate_result.reason}")
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

            # Gate passthrough
            if func_name == "create_order":
                result = create_order(**func_args)
            elif func_name == "get_order_status":
                result = get_order_status(**func_args)

            print(f"TOOL EXCUTOR: {func_name}({func_args}) => {result}")  # type: ignore
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
        print(f"Final Answer: {test_result['final_answer']}")
        return test_result
    else:
        test_result["final_answer"] = response.choices[0].message.content
        print(f"Final Answer: {test_result['final_answer']}")
        return test_result
    
