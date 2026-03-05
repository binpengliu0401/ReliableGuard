from dotenv import load_dotenv
from mistralai.models import UserMessage, ToolMessage
from mistralai import Mistral
import os
from typing import Any
from src.tools.order_tools import tools, create_order, get_order_status
import json

def run_baseline(msg: str):
    
    result = {
        "input": msg,
        "tool_called": False,
        "args_passed": None,
        "final_answer": None,
        "func_name": None
    }
    
    print(f"\n{'='*50}")
    print(f"[INPUT]    {msg}")
    
    load_dotenv()
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    message: list[Any] = [UserMessage(content=msg)]
    
    response = client.chat.complete(
        model="mistral-small-latest", messages=message, tools=tools, tool_choice="auto"  # type: ignore
    )
    
    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments) # type: ignore
            
            # Excute directly, no Gate and Verifier
            if func_name == "create_order":
                exec_result = create_order(**func_args)
            elif func_name == "get_order_status":
                exec_result = get_order_status(**func_args)
            
            print(f"[EXECUTOR] {func_name}({func_args}) => {exec_result}") # type: ignore
            
            result["tool_called"] = True
            result["args_passed"] = func_args
            result["func_name"] = func_name
            
            message.append(response.choices[0].message)
            message.append(
                ToolMessage(
                    tool_call_id=tool_call.id,
                    content=json.dumps(exec_result), # type: ignore
                )
            )
        
        final = client.chat.complete(
            model = "mistral-small-latest",
            messages=message,
        )
        result["final_answer"] = final.choices[0].message.content
        print(f"[ANSWER]    {result['final_answer']}")
        return result
    else:
        result["final_answer"] = response.choices[0].message.content
        print(f"[NOT TRIGGERED] model refused to call tool")
        print(f"[ANSWER]   {result['final_answer']}")
        return result
            