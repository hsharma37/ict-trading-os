# ICT Trading OS — New MacBook Setup Guide

Complete step-by-step guide to set up your MacBook, deploy the backend to Vercel, and connect your frontend.

---

## Step 1: Install Homebrew (Package Manager)

Homebrew installs everything else. Open **Terminal** (Press `Cmd + Space`, type "Terminal", hit Enter).

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

When it asks for your password, type it (you won't see characters — this is normal) and press Enter.

After installation finishes, run this to add Homebrew to your PATH:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Verify:
```bash
brew --version
```
You should see something like `Homebrew 4.x.x`.

---

## Step 2: Install Node.js & npm (for Vercel CLI)

```bash
brew install node
```

Verify:
```bash
node --version   # Should show v20.x.x or higher
npm --version    # Should show 10.x.x or higher
```

---

## Step 3: Install Python 3.11

```bash
brew install python@3.11
```

Verify:
```bash
python3.11 --version   # Should show Python 3.11.x
```

Make it the default `python3`:
```bash
echo 'export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
python3 --version
```

Also install pip:
```bash
python3 -m ensurepip --upgrade
```

---

## Step 4: Install Git

```bash
brew install git
```

Verify:
```bash
git --version   # Should show 2.x.x
```

Configure Git (use your actual name and email):
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

---

## Step 5: Install Vercel CLI

```bash
npm install -g vercel
```

Verify:
```bash
vercel --version
```

Login to Vercel:
```bash
vercel login
```
This opens a browser window. Click **Continue**, then go back to Terminal.

---

## Step 6: Download the Backend Code

Create a folder for your project:
```bash
mkdir -p ~/Projects/ict-trading-os
cd ~/Projects/ict-trading-os
```

Download the backend (copy the `ict-trading-os-vercel` folder from the output to this location):

If you have the folder as a ZIP, extract it:
```bash
# If you downloaded a ZIP:
# unzip ~/Downloads/ict-trading-os-vercel.zip -d ~/Projects/ict-trading-os/
# cd ~/Projects/ict-trading-os/ict-trading-os-vercel
```

Or if you cloned from GitHub:
```bash
git clone https://github.com/YOUR_USERNAME/ict-trading-os-backend.git
cd ict-trading-os-backend
```

---

## Step 7: Test Locally (Optional but Recommended)

Install Python dependencies:
```bash
python3 -m pip install -r requirements.txt
```

Run the server locally:
```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

Open a browser and test:
- http://localhost:8000/ → Should show API info
- http://localhost:8000/health → Should show `{"status": "healthy"}`
- http://localhost:8000/market/price/NQ1! → Should show live price

Press `Ctrl + C` in Terminal to stop the server.

---

## Step 8: Deploy to Vercel

From inside your project folder:
```bash
cd ~/Projects/ict-trading-os/ict-trading-os-vercel
vercel
```

Vercel will ask:
- **Set up and deploy?** → Type `Y` and press Enter
- **Which scope?** → Select your account (press Enter)
- **Link to existing project?** → Type `N` (first time)
- **What's your project name?** → Type `ict-trading-os-api` and press Enter

Wait for deployment. You'll see a URL like:
```
https://ict-trading-os-api-yourname.vercel.app
```

**For production deploy:**
```bash
vercel --prod
```

This gives you the permanent production URL.

---

## Step 9: Verify Your API is Live

Test these URLs in your browser (replace with your actual URL):

```
https://ict-trading-os-api-yourname.vercel.app/
https://ict-trading-os-api-yourname.vercel.app/health
https://ict-trading-os-api-yourname.vercel.app/market/price/NQ1!
https://ict-trading-os-api-yourname.vercel.app/ict/analyze/NQ1!
https://ict-trading-os-api-yourname.vercel.app/signals/analyze/NQ1!
```

All should return JSON data.

---

## Step 10: Connect Your Frontend

### Option A: Edit Your Existing HTML

Open your `ICT_Trading_OS_v7.html` file. Find the `<script>` section and add this at the top:

```javascript
// ============ API CONFIGURATION ============
const API_BASE = 'https://ict-trading-os-api-yourname.vercel.app'; // REPLACE WITH YOUR URL

// Override synthetic prices with real data
async function fetchLivePrice(symbol) {
    const res = await fetch(`${API_BASE}/market/price/${symbol}`);
    const data = await res.json();
    return data.price;
}

// Get ICT pattern analysis
async function fetchICTAnalysis(symbol) {
    const res = await fetch(`${API_BASE}/ict/analyze/${symbol}`);
    return res.json();
}

// Get trading signal
async function fetchSignal(symbol) {
    const res = await fetch(`${API_BASE}/signals/analyze/${symbol}`);
    return res.json();
}

// Get quant metrics
async function fetchQuantMetrics() {
    const res = await fetch(`${API_BASE}/quant/metrics`);
    return res.json();
}

// Get coach recommendations
async function fetchCoach() {
    const res = await fetch(`${API_BASE}/quant/coach`);
    return res.json();
}
```

### Option B: Use the Full API Client

Copy the contents of `frontend-api.js` (from the backend folder) into a `<script>` tag in your HTML, or save it as `api.js` and include:

```html
<script src="api.js"></script>
```

Then update the `API_BASE` variable at the top of that file with your Vercel URL.

---

## Step 11: Update Frontend for Real-Time Data

Replace the synthetic price generator in your HTML with this:

```javascript
// Replace the existing tickAllInstruments() function
async function tickAllInstruments() {
    const symbols = Object.keys(INSTRUMENTS);
    for (const sym of symbols) {
        try {
            const data = await fetch(`${API_BASE}/market/price/${sym}`).then(r => r.json());
            if (data.price) {
                INSTRUMENTS[sym].prev = INSTRUMENTS[sym].price;
                INSTRUMENTS[sym].price = data.price;
            }
        } catch (e) {
            // Fallback to synthetic if API fails
            const inst = INSTRUMENTS[sym];
            inst.prev = inst.price;
            const move = (Math.random() - 0.49) * inst.vol;
            inst.price = Math.max(0.0001, +(inst.price + move).toFixed(inst.digits));
        }
    }
}
```

---

## Step 12: Deploy Frontend to Netlify

Your frontend HTML also needs to go live. Here's how:

### Method: Drag & Drop

1. Create a folder `ict-trading-os-frontend`
2. Copy your `ICT_Trading_OS_v7.html` into it
3. Rename it to `index.html`
4. Create a file named `_redirects` with this content:
   ```
   /* /index.html 200
   ```
5. Go to [netlify.com](https://netlify.com), log in
6. Drag the entire folder onto the Netlify dashboard
7. You get a URL like `https://ict-trading-os-abc123.netlify.app`

### Important: Update CORS

After you have your Netlify URL, update your Vercel backend to allow it:

```bash
vercel env add CORS_ORIGINS
```
When prompted, type your Netlify URL:
```
https://ict-trading-os-abc123.netlify.app
```

Then redeploy:
```bash
vercel --prod
```

---

## Quick Reference: All Commands

```bash
# Install everything (one-time)
brew install node python@3.11 git
npm install -g vercel

# Deploy backend
 cd ~/Projects/ict-trading-os/ict-trading-os-vercel
vercel --prod

# Update environment variable
vercel env add CORS_ORIGINS

# View logs
vercel logs --production
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: brew` | Close Terminal, reopen it |
| `command not found: vercel` | Run `npm install -g vercel` again |
| `Module not found` on deploy | Make sure `requirements.txt` is in the project root |
| API returns 500 error | Check Vercel logs: `vercel logs --production` |
| Frontend can't connect to API | Check CORS_ORIGINS matches your Netlify URL exactly |
| Prices are synthetic | Yahoo Finance API might be rate-limited; wait 1 minute and retry |

---

## Next Steps After Deployment

1. **Add Supabase** for persistent data storage (free tier, 500MB)
2. **Add YouTube transcript ingestion** using the `youtube-transcript-api` Python package
3. **Add Anthropic/OpenAI** for LLM-powered coaching
4. **Set up GitHub Actions** for auto-deploy on push

Your trading OS is now live with real market data and ICT pattern detection!
