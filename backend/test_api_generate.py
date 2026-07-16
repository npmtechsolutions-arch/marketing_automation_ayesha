import asyncio
import httpx

async def test_generate_content_api():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Login to get access token
    print("Logging in...")
    async with httpx.AsyncClient() as client:
        # FastAPI endpoint expects JSON payload
        login_data = {
            "email": "user@gmail.com",
            "password": "user123"
        }
        res = await client.post(f"{base_url}/auth/login", json=login_data)
        if res.status_code != 200:
            print("Login failed:", res.status_code, res.text)
            return
        
        login_res = res.json()
        token = login_res["access_token"]
        print("Login successful. Token acquired.")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 2. Get current user's accounts to find the account_id
        res = await client.get(f"{base_url}/users/me", headers=headers)
        if res.status_code != 200:
            print("Failed to get current user info:", res.status_code, res.text)
            return
        
        user_info = res.json()
        print("User Info:", user_info)
        
        # In this API structure, let's find accounts of the user. Or maybe we can fetch them via /accounts or /accounts/
        # Let's list accounts or fetch from check_users db seed
        # Let's query accounts
        res = await client.get(f"{base_url}/accounts/", headers=headers)
        print("Accounts response:", res.status_code, res.text)
        if res.status_code != 200:
            # Let's try to query /accounts or check if we can query /users/me
            pass
        
        # From seed.py: John Marketing's account is:
        # user_account_id = uuid.UUID('...') - let's check what it actually is in the database,
        # or we can query the /accounts/ endpoint if it exists.
        # Let's check check_routes.py output to see how to list accounts or let's use the account ID from user's logs:
        # ':8000/api/v1/accounts/b45df8e1-ae74-4160-a89a-9541eb0cb74a/ai/generate-content' -> account_id = "b45df8e1-ae74-4160-a89a-9541eb0cb74a"
        account_id = "b45df8e1-ae74-4160-a89a-9541eb0cb74a"
        
        payload = {
            "prompt": "Write a post about digital marketing tips.",
            "platforms": ["instagram", "facebook"],
            "tone": "professional",
            "business_id": None
        }
        
        print(f"\nSending generate-content request for account: {account_id}...")
        try:
            res = await client.post(
                f"{base_url}/accounts/{account_id}/ai/generate-content",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            print("Response Status Code:", res.status_code)
            print("Response Headers:", res.headers)
            print("Response Text:", res.text)
        except Exception as e:
            print("Request failed with exception:", e)

if __name__ == "__main__":
    asyncio.run(test_generate_content_api())
