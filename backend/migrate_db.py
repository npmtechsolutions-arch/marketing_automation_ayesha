import asyncio
from sqlalchemy import text
from app.core.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Checking/migrating platform-specific columns in 'posts' table...")
        
        # Consolidate all custom post fields added across iterations
        columns = [
            # Instagram-specific fields
            ("instagram_post_type", "VARCHAR(50)"),
            ("instagram_music_track", "VARCHAR(255)"),
            ("instagram_music_url", "TEXT"),
            ("instagram_music_start_offset", "INTEGER"),
            ("instagram_music_end_offset", "INTEGER"),
            ("instagram_video_url", "TEXT"),
            
            # Facebook-specific fields
            ("facebook_post_type", "VARCHAR(50)"),
            ("facebook_music_track", "VARCHAR(255)"),
            ("facebook_music_url", "TEXT"),
            ("facebook_music_start_offset", "INTEGER"),
            ("facebook_music_end_offset", "INTEGER"),
            ("facebook_video_url", "TEXT"),
            
            # YouTube, LinkedIn, and Twitter fields
            ("youtube_post_type", "VARCHAR(50)"),
            ("linkedin_post_type", "VARCHAR(50)"),
            ("twitter_post_type", "VARCHAR(50)")
        ]
        
        for col_name, col_type in columns:
            query = text(f"""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name='posts' AND column_name='{col_name}'
                );
            """)
            result = await conn.execute(query)
            exists = result.scalar()
            
            if not exists:
                print(f"Adding column '{col_name}' of type {col_type}...")
                await conn.execute(text(f"ALTER TABLE posts ADD COLUMN {col_name} {col_type};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists.")
                
        print("Database migration check completed successfully.")

if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(migrate())
