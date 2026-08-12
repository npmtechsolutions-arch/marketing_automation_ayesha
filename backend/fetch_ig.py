import httpx
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-IG-App-ID": "936619743392459",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_ig_pic():
    # 1. Try web_profile_info
    try:
        url = "https://i.instagram.com/api/v1/users/web_profile_info/?username=sivan_is_only_onr_lord"
        r = httpx.get(url, headers=headers, timeout=10.0)
        print("API Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            user = data.get("data", {}).get("user", {})
            hd_pic = user.get("profile_pic_url_hd") or user.get("profile_pic_url")
            print("HD Pic:", hd_pic)
            print("Full Name:", user.get("full_name"))
            print("Followers:", user.get("edge_followed_by", {}).get("count"))
            print("Following:", user.get("edge_follow", {}).get("count"))
            print("Posts:", user.get("edge_owner_to_timeline_media", {}).get("count"))
            return hd_pic, user
    except Exception as e:
        print("API Error:", e)

    # 2. Try scraping HTML
    try:
        r2 = httpx.get("https://www.instagram.com/sivan_is_only_onr_lord/", headers=headers, follow_redirects=True, timeout=10.0)
        print("HTML Status:", r2.status_code)
        m = re.search(r'property="og:image" content="([^"]+)"', r2.text)
        if m:
            print("og:image:", m.group(1))
            return m.group(1), None
    except Exception as e:
        print("HTML Error:", e)

    return None, None

if __name__ == "__main__":
    fetch_ig_pic()
