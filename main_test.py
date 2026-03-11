from dotenv import load_dotenv
import os

load_dotenv()
print("API KEY:", os.getenv("OPENAI_API_KEY"))

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

idea = input("Enter a game idea:\n")

response = llm.invoke(f"Describe how to build this game:\n{idea}")

print(response.content)