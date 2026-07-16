import asyncio
import httpx
import os

async def test_anthropic():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    # Note: Model in code is "claude-sonnet-4-6" - let's check what Anthropic API returns for this model.
    model = "claude-sonnet-4-6"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model,
        "max_tokens": 2000,
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "Hello, write a short sentence."}
        ]
    }
    print(f"Calling Anthropic API with model '{model}'...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=20.0
            )
            print("Status Code:", response.status_code)
            print("Headers:", response.headers)
            print("Response:", response.text)
    except Exception as e:
        print("An error occurred during API request:", e)

# Also let's test a valid model like 'claude-3-5-sonnet-20241022'
async def test_anthropic_valid_model():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = "claude-3-5-sonnet-20241022"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model,
        "max_tokens": 2000,
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "Hello, write a short sentence."}
        ]
    }
    print(f"\nCalling Anthropic API with valid model '{model}'...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=20.0
            )
            print("Status Code:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        print("An error occurred during API request:", e)

async def main():
    await test_anthropic()
    await test_anthropic_valid_model()

if __name__ == "__main__":
    asyncio.run(main())
