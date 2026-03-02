from dotenv import load_dotenv
from mistralai.models import UserMessage, ToolMessage
from mistralai import Mistral
import os
from typing import Any
from src.tools.order_tools import tools, create_order, get_order_status
import json


def run_agent(msg: str):

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

            if func_name == "create_order":
                result = create_order(**func_args)
            elif func_name == "get_order_status":
                result = get_order_status(**func_args)

            print(f"TOOL EXCUTOR: {func_name}({func_args}) => {result}")  # type: ignore

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
        print(f"Final Answer: {final.choices[0].message.content}")
