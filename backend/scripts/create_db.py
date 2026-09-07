import asyncio
import asyncpg

async def main():
    try:
        # Connect to the default 'postgres' database
        conn = await asyncpg.connect(
            user='postgres',
            password='1234',
            database='postgres',
            host='localhost'
        )
        print("Connected to default 'postgres' database successfully.")
        
        # Check if database 'marketing_automation' exists
        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'marketing_automation'"
        )
        
        if not result:
            # We must execute CREATE DATABASE outside a transaction block
            # asyncpg allows this if we don't start a transaction.
            await conn.execute("CREATE DATABASE marketing_automation")
            print("Successfully created database 'marketing_automation'.")
        else:
            print("Database 'marketing_automation' already exists.")
            
        await conn.close()
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == '__main__':
    asyncio.run(main())
