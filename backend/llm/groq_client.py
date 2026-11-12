import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found!")

groq_llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=GROQ_API_KEY,

    temperature=0.5,
    max_tokens=1200,

    reasoning_effort="low",
    reasoning_format="hidden",

    model_kwargs={
        "response_format": {"type": "json_object"}
    },

    max_retries=1,
    timeout=60
)