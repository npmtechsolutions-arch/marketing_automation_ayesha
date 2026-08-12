import asyncio
import os
import httpx
from app.core.database import AsyncSessionLocal
from app.models.platform import SocialAccount, SocialPlatform
from sqlalchemy import select

async def download_and_save():
    os.makedirs("uploads", exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    # 1. Instagram Profile Pic (Virat Kohli in Indian jersey)
    ig_url = "https://instagram.fsxv4-2.fna.fbcdn.net/v/t51.82787-19/742345679_18095718968193503_7992582098270551062_n.jpg?stp=dst-jpg_s320x320_tt6&efg=eyJ2ZW5jb2RlX3RhZyI6InByb2ZpbGVfcGljLmRqYW5nby43MzYuYzIifQ&_nc_ht=instagram.fsxv4-2.fna.fbcdn.net&_nc_cat=111&_nc_oc=Q6cZ2gE7w1zpGU7pjFgv0ZFbnaEAJZ_W8l6LoyxilVGwbxO-5Jsl3CAaWMy9irKkmwGsUCcHM41Qya9aXXMtcT2SD9Tb&_nc_ohc=GgzuBMdZfhkQ7kNvwHHCGFn&_nc_gid=nNXkE1hw_WzwxVhfKGlPgg&edm=AOQ1c0wBAAAA&ccb=7-5&oh=00_AQETpuvm3jWTcbNHEokNWdt_uUfYlhY5D2O-6gQmaPUvCQ&oe=6A825DD8&_nc_sid=8b3546"
    ig_path = os.path.join("uploads", "instagram_sivan_is_only_onr_lord.jpg")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(ig_url, headers=headers, follow_redirects=True, timeout=15.0)
            if r.status_code == 200:
                with open(ig_path, "wb") as f:
                    f.write(r.content)
                print(f"Saved Instagram avatar: {len(r.content)} bytes")
            else:
                print(f"Failed to download IG pic: status {r.status_code}")
    except Exception as e:
        print("IG download error:", e)

    # 2. YouTube Channel Avatar (GL MONSTER)
    yt_url = "https://yt3.ggpht.com/ytc/AIdro_n729880_hRzWesqCNbjV-S1QJ4_iFXJI0ACNQ_amgCGeUQGLx96oMiJ7gJ4FbIrKVpqA=s800-c-k-c0x00ffffff-no-rj"
    yt_path = os.path.join("uploads", "youtube_glmonster.jpg")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(yt_url, headers=headers, follow_redirects=True, timeout=15.0)
            if r.status_code == 200:
                with open(yt_path, "wb") as f:
                    f.write(r.content)
                print(f"Saved YouTube avatar: {len(r.content)} bytes")
            else:
                print(f"Failed to download YT pic: status {r.status_code}")
    except Exception as e:
        print("YT download error:", e)

    # 3. LinkedIn Profile Avatar
    li_url = "https://media.licdn.com/dms/image/v2/D5603AQGFHBd_2c76SA/profile-displayphoto-shrink_100_100/profile-displayphoto-shrink_100_100/0/1720507649417?e=1788393600&v=beta&t=2hN1ObVp6Zn--6jxPOoE97Y9KBm1Vj3Rg3NQRsFWPb4"
    li_path = os.path.join("uploads", "linkedin_siva_bharathi.jpg")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(li_url, headers=headers, follow_redirects=True, timeout=15.0)
            if r.status_code == 200:
                with open(li_path, "wb") as f:
                    f.write(r.content)
                print(f"Saved LinkedIn avatar: {len(r.content)} bytes")
            else:
                print(f"Failed to download LinkedIn pic: status {r.status_code}")
    except Exception as e:
        print("LinkedIn download error:", e)

    # Update database rows with absolute permanent URLs
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(SocialAccount, SocialPlatform).join(SocialPlatform, SocialAccount.platform_id == SocialPlatform.id))
        rows = res.all()
        for sa, sp in rows:
            slug = (sp.slug or "").lower()
            if "instagram" in slug:
                sa.account_name = "sivan_is_only_onr_lord"
                sa.account_handle = "S. Siva virat"
                sa.profile_image_url = "http://localhost:8000/uploads/instagram_sivan_is_only_onr_lord.jpg"
                sa.metadata_ = {
                    "followers": 16,
                    "following": 1,
                    "posts_count": 9,
                }
                print("Updated Instagram row in DB!")
            elif "youtube" in slug:
                sa.profile_image_url = "http://localhost:8000/uploads/youtube_glmonster.jpg"
                print("Updated YouTube row in DB!")
            elif "linkedin" in slug:
                sa.profile_image_url = "http://localhost:8000/uploads/linkedin_siva_bharathi.jpg"
                print("Updated LinkedIn row in DB!")

        await db.commit()
        print("Successfully committed updated social accounts!")

if __name__ == "__main__":
    asyncio.run(download_and_save())
