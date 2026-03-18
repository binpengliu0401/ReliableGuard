from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="qwen-plus-2025-07-28",
    messages=[{"role": "user", "content": "hello, reply with one sentence"}],
)

print("SUCCESS:", response.choices[0].message.content)