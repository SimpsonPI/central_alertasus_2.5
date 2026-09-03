import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

async def testar():
    url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={API_KEY}"
    payload = {
        "model": "gemini-3.6-flash",
        "input": {
            "messages": [{"role": "user", "content": [{"text": "Diga olá."}]}]
        }
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers={"Api-Revision": "2026-05-20"})
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text[:500]}")

asyncio.run(testar())