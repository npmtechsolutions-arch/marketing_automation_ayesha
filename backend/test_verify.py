import asyncio
from app.api.v1.endpoints.social_accounts import get_instagram_public_metrics

async def main():
    username = "sivabharathi_is_the_king"
    print("Testing get_instagram_public_metrics for sivabharathi_is_the_king...")
    res = await get_instagram_public_metrics(username)
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
