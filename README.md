# Twitt 🐦

Lightweight, **zero-dependency** native Python client for X (Twitter) using internal GraphQL and authenticated HTTP endpoints.

Fast, reliable automation for engagement, replies, timeline retrieval, and social graph management without heavy browser overhead.

---

## ⚡ Key Highlights

- **Zero Third-Party Dependencies:** Uses standard library only (`urllib`, `ssl`, `json`, `base64`). No `pip install` required.
- **No Headless Browser Required:** Does not spawn Chromium, Playwright, or Puppeteer for routine actions. Response times are in milliseconds with near-zero memory footprint.
- **Native GraphQL & Web Endpoints:** Uses the exact endpoints and query signatures powering the modern X Web client.
- **Safe & Clean:** Built-in `.gitignore` rules prevent accidental secret/cookie leaks.

---

## 🚀 Features

- **Engagement:**
  - `like(tweet_id)` & `unlike(tweet_id)`
  - `repost(tweet_id)` & `unrepost(tweet_id)`
  - `verify_like(tweet_id)` & `verify_repost(tweet_id)`
- **Posting & Conversations:**
  - `reply(tweet_id, text)` (threaded reply)
  - `post(text)` (standalone tweet)
  - `delete_tweet(tweet_id)`
- **Social Graph:**
  - `follow(username_or_id)`
  - `unfollow(username_or_id)`
- **Information Retrieval:**
  - `read_tweet_text(tweet_id)`
  - `user_by_screen_name(username)`
  - `user_timeline_tweets(username_or_id, count=10)` (with cursor pagination)
  - `whoami()` (session health check)

---

## 🔑 Authentication Setup

Twitt authenticates via active session cookies (`auth_token` and `ct0`).

### 1. Get your cookies:
Open `https://x.com` in your browser where you are logged in:
1. Open DevTools (`F12` or `Ctrl+Shift+I`).
2. Go to **Application** (or **Storage**) → **Cookies** → `https://x.com`.
3. Copy the values of `auth_token` and `ct0`.

### 2. Configure credentials:

#### Option A: Environment Variables (Recommended)
```bash
export AUTH_TOKEN="your_auth_token_here"
export CT0="your_ct0_here"
```

#### Option B: Local `.env` file
Create a `.env` file in your working directory (automatically ignored by git):
```env
AUTH_TOKEN=your_auth_token_here
CT0=your_ct0_here
```

#### Option C: Base64 Cookie String
```bash
export API_KEY="base64_encoded_cookie_string"
```

---

## 💻 CLI Usage

### Check Session Health
```bash
python3 x_native.py whoami
```

### Engagement & Actions
```bash
# Like a tweet
python3 x_native.py like 1840000000000000000

# Retweet / Repost
python3 x_native.py repost 1840000000000000000

# Reply to tweet
python3 x_native.py reply 1840000000000000000 "Great project!"

# Follow a user (by handle or ID)
python3 x_native.py follow jack

# Unfollow a user
python3 x_native.py unfollow jack

# Delete a tweet
python3 x_native.py delete 1840000000000000000
```

### Reading Tweets & Users
```bash
# Read tweet content
python3 x_native.py read 20

# Get user details
python3 x_native.py user jack

# Fetch user timeline
python3 x_native.py timeline jack 5
```

---

## 🐍 Python Library Usage

```python
import x_native

# Check session
viewer, err = x_native.whoami()
print("Logged in as:", viewer["user_results"]["result"]["core"]["screen_name"])

# Like & Repost
ok, detail = x_native.like("20")
ok, detail = x_native.repost("20")

# Threaded reply
ok, detail = x_native.reply("20", "Hello from Python!")

# Follow
ok, detail = x_native.follow("jack")

# Read tweet
tweet_text = x_native.read_tweet_text("20")
print(tweet_text)

# Fetch user timeline
timeline = x_native.user_timeline_tweets("jack", count=5)
for t in timeline["list"]:
    print(f"[{t['id']}] {t['fullText']}")
```

---

## 🧪 Testing

Run unit tests (all mocked, no live credentials needed):

```bash
python3 -m unittest test_offline.py
```

---

## ⚠️ Security Notice

- **Never commit your `.env`, cookies, or tokens to version control.**
- Twitt includes strict `.gitignore` rules by default. Always verify `git status` before pushing changes.

---

## 📄 License

MIT License.
