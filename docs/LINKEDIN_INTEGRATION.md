# LinkedIn Integration — Setup & Usage Guide

This app can connect a client's LinkedIn account (personal profile **or** company
page) via one‑click OAuth and publish **text + image posts** to it. This guide
walks you through creating the LinkedIn Developer app, wiring the credentials,
and posting.

> **What works today**
> - ✅ One‑click "Sign in with LinkedIn" connect flow (no manual tokens)
> - ✅ Publish **text** posts to a personal profile
> - ✅ Publish **image** posts to a personal profile
> - ✅ Publish text/image posts to a **company page** (requires one extra product, see Step 3)
>
> **What is NOT possible with a standard app**
> - ⚠️ **Job postings** — require LinkedIn **Talent Solutions** partnership (a vetted, manually‑approved program).
> - ⚠️ **Ads** — require the LinkedIn **Marketing Developer Platform** partnership (also vetted/approved).
> - ⚠️ **Video** posting — not implemented yet.
>
> Jobs/Ads cannot be enabled just by writing code — LinkedIn must approve your
> company for those programs first. Until then, the app surfaces a clear message
> instead of silently failing.

---

## Step 1 — Create a LinkedIn Developer App

1. Go to <https://www.linkedin.com/developers/apps> and click **Create app**.
2. Fill in:
   - **App name**: e.g. "MarketEngine AI"
   - **LinkedIn Page**: select (or create) the company page that owns the app.
   - **App logo**: upload any logo.
   - Accept the legal terms and click **Create app**.
3. Open the app → **Settings** tab → **Verify** your company page (one‑time click).

## Step 2 — Get your Client ID & Secret

1. Open the app → **Auth** tab.
2. Copy **Client ID** and **Primary Client Secret**.
3. Paste them into the backend `.env` file at the repo root:

   ```env
   LINKEDIN_CLIENT_ID=your_client_id_here
   LINKEDIN_CLIENT_SECRET=your_client_secret_here
   LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/linkedin/callback
   ```

4. In the **Auth** tab, under **OAuth 2.0 settings → Authorized redirect URLs for your app**,
   click **Add redirect URL** and add **exactly**:

   ```
   http://localhost:8000/api/v1/linkedin/callback
   ```

   > This must match `LINKEDIN_REDIRECT_URI` **character for character**. When you
   > deploy to production, add your live URL too (e.g.
   > `https://api.yourdomain.com/api/v1/linkedin/callback`) and update the `.env`.

## Step 3 — Add the Products (permissions)

Open the app → **Products** tab and request:

| Product | Needed for | Approval |
|---|---|---|
| **Sign In with LinkedIn using OpenID Connect** | Identifying the connected user | Instant / auto |
| **Share on LinkedIn** | Posting to a **personal profile** | Instant / auto |
| **Community Management API** | Posting to a **company page** | Self‑serve request (grants `w_organization_social`, `rw_organization_admin`) |

- For **personal profile** posting you only need the first two (auto‑approved).
- For **company page** posting you also need **Community Management API**, and the
  connecting user must be an **Administrator** of that page.

After adding a product, confirm the scopes appear under **Auth → OAuth 2.0 scopes**.
The app requests:
- Personal: `openid profile email w_member_social`
- Organization: `openid profile email r_organization_social w_organization_social rw_organization_admin`

## Step 4 — Restart the backend

Environment variables are read at startup, so restart the API after editing `.env`:

```bash
cd backend
uvicorn app.main:app --reload
```

---

## Step 5 — Connect a client's LinkedIn account (in the app)

1. Log in → go to **Social Accounts**.
2. Click **Add Account** → select the **LinkedIn** platform.
3. In the LinkedIn box, click:
   - **Connect Personal Profile** — to post to the signed‑in user's own feed, **or**
   - **Connect Company Page** — to post to a page they administer.
4. You're redirected to LinkedIn → approve → you land back on the Social Accounts
   page with **"LinkedIn Account connected successfully!"**. The account now shows
   as **Verified** with its name and photo.

> Connecting a **Company Page** creates one connected account per page the user
> administers. If none is found you'll see a "no admin orgs" message — the user
> isn't an admin of any page, or the Community Management API product isn't enabled.

## Step 6 — Publish a post

1. Go to **Create Post**, write your content, and (optionally) attach **one image**.
2. Select the connected LinkedIn account as a target.
3. Publish. The post goes live via LinkedIn's UGC Posts API, and the resulting
   LinkedIn URL is stored on the post.

---

## How it works (for developers)

| Piece | File |
|---|---|
| OAuth consent URL + callback | `backend/app/api/v1/endpoints/linkedin_oauth.py` |
| Router registration | `backend/app/main.py` (`/linkedin/authorize`, `/linkedin/callback`) |
| Post publishing (text/image, person/org) | `backend/app/services/platform_service.py` → `publish_to_linkedin` |
| Publish dispatch | `backend/app/api/v1/endpoints/posts.py` (`"linkedin" in platform_slug`) |
| Token refresh | `backend/app/api/v1/endpoints/social_accounts.py` → `refresh-token` |
| Connect UI | `frontend/src/pages/platforms/SocialAccountsPage.tsx` |

- **Identity across the redirect** is carried in a 15‑minute signed JWT `state`
  (signed with `JWT_SECRET_KEY`), so the public callback knows which workspace/user
  and platform initiated the flow.
- The connected account stores `config.author_urn`
  (`urn:li:person:{id}` or `urn:li:organization:{id}`) and `config.target`; the
  publisher uses these to post as the right author.
- Tokens: LinkedIn access tokens last ~60 days. If your app has **programmatic
  refresh** enabled, a `refresh_token` is stored and the **Refresh Token** action
  renews it; otherwise the user re‑connects.

## Troubleshooting

| Message | Cause / Fix |
|---|---|
| "LinkedIn is not configured" | `LINKEDIN_CLIENT_ID/SECRET` missing in `.env`; restart backend after adding. |
| `invalid_state` after redirect | The consent link expired (>15 min) or `JWT_SECRET_KEY` changed. Retry. |
| `token_exchange_failed` | The redirect URL in the LinkedIn app doesn't match `LINKEDIN_REDIRECT_URI` exactly. |
| `no_admin_orgs` (company page) | User isn't an Admin of any page, or Community Management API not enabled. |
| Post fails with a scope error | Requested scope isn't granted — add the matching **Product** (Step 3) and reconnect. |
| "LinkedIn video publishing is not supported yet" | Attach an image or post text only. |

---

# X (Twitter) Integration

Same one-click OAuth pattern as LinkedIn. Publishes **text tweets** via the X API v2.

## Create the X app

1. Go to <https://developer.twitter.com/en/portal/dashboard> → create a **Project + App**.
2. In the app's **User authentication settings**, click **Set up** and choose:
   - **App permissions**: **Read and write** (required to post).
   - **Type of App**: **Web App / Automated App** (confidential client).
   - **Callback URI / Redirect URL**: `http://localhost:8000/api/v1/twitter/callback` (must match `TWITTER_REDIRECT_URI`).
   - **Website URL**: any valid URL.
3. Under **Keys and tokens**, copy the **OAuth 2.0 Client ID** and **Client Secret** into `.env`:

   ```env
   TWITTER_CLIENT_ID=your_client_id
   TWITTER_CLIENT_SECRET=your_client_secret
   TWITTER_REDIRECT_URI=http://localhost:8000/api/v1/twitter/callback
   ```

## Connect & post

- **Social Accounts → Add Account → X (Twitter) → Connect X (Twitter) Account.**
- Uses OAuth 2.0 **PKCE** with scopes `tweet.read tweet.write users.read offline.access`.
- Only **text** is posted today (media upload uses X's separate chunked-upload API — not implemented).

> ⚠️ **X free-tier limits:** X's Free API plan allows only a very small number of posts and is heavily rate-limited. Reliable automated posting typically needs the **Basic** paid plan. This is an X policy/pricing limit, not a code issue.

---

# YouTube Integration

Same OAuth pattern. "Publishing" to YouTube = **uploading a video** (there is no public API for community posts), so a **video attachment is required**.

## Create the Google OAuth client

1. Go to <https://console.cloud.google.com/> → create/select a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen** → configure (External), and add your Google account under **Test users** while the app is in Testing.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - **Application type**: Web application.
   - **Authorized redirect URIs**: `http://localhost:8000/api/v1/youtube/callback` (must match `YOUTUBE_REDIRECT_URI`).
5. Copy the **Client ID** and **Client Secret** into `.env`:

   ```env
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   YOUTUBE_REDIRECT_URI=http://localhost:8000/api/v1/youtube/callback
   ```

## Connect & post

- **Social Accounts → Add Account → YouTube → Connect YouTube Channel.**
- Scopes: `youtube.upload youtube.readonly` (+ `openid email profile`), with `access_type=offline` so a refresh token is issued.
- To publish: create a post with a **video** attachment, target the YouTube account, and publish — the video is uploaded via Google's resumable upload.

> ⚠️ **Unverified app:** Until you complete Google's OAuth **verification**, uploads from the `youtube.upload` scope are locked to **private** visibility, and only **Test users** on the consent screen can connect. Submit the app for verification to publish public videos for any user.

---

## Where each platform is wired (developer reference)

| Platform | OAuth module | Publisher |
|---|---|---|
| LinkedIn | `linkedin_oauth.py` | `publish_to_linkedin` |
| Facebook | `facebook_oauth.py` | `publish_to_facebook` |
| Instagram | `instagram_oauth.py` | `publish_to_instagram` |
| X (Twitter) | `twitter_oauth.py` | `publish_to_twitter` |
| YouTube | `youtube_oauth.py` | `publish_to_youtube` |

All connect flows carry identity in a 15-min signed `state` JWT; X additionally
carries its PKCE `code_verifier` there. Publish dispatch is in
`backend/app/api/v1/endpoints/posts.py` (`publish_to_platforms`), and per-platform
token refresh is in `social_accounts.py` (`refresh-token`).
