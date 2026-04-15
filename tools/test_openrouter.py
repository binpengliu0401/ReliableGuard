#!/usr/bin/env python3
import os

from openai import OpenAI


def main() -> int:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY is not set.")
        return 1

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello"}],
        )
        content = response.choices[0].message.content
        if content is None:
            print("No response content returned.")
        else:
            print(content)
        return 0
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
