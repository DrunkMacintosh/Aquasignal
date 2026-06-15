# Deploying AquaSignal — free hosting, no credit card

This guide takes you from zero to a live system using only free tiers:

| Component | Service | What it does |
|---|---|---|
| Database | [Supabase](https://supabase.com) | PostgreSQL + PostGIS (spatial queries) |
| API | [Render](https://render.com) | runs the FastAPI backend |
| Dashboard | [Vercel](https://vercel.com) | serves the React app on a global CDN |
| Monthly pipeline | GitHub Actions | fetches satellite data, re-scores, on the 5th |
| ML models | [Hugging Face Hub](https://huggingface.co) | pulled at startup (Render) and by CI; see §7 — **required**, the models are no longer in git |

**Before you start** you need: a GitHub account with this repository pushed to
it (**public** repo — scheduled workflow minutes are free only on public
repos), and about 45 minutes. Every secret value you create along the way,
paste into a scratch note — you will enter each one exactly once at the end
of the step that creates it.

---

## 1. Supabase — the database (~10 min)

1. Go to **https://supabase.com** → **Start your project** → sign in with GitHub.
2. Click **New project**. Name: `aquasignal`. **Database password**: click
   **Generate a password** and save it in your note. Region: pick the one
   closest to your users (e.g. *Southeast Asia (Singapore)*). Click
   **Create new project** and wait ~2 minutes.
3. Left sidebar → **SQL Editor** → **New query** → paste the entire contents
   of [`supabase/setup.sql`](supabase/setup.sql) → click **Run**. You should
   see a PostGIS version string. (Tables are created automatically later —
   don't create any by hand.)
4. Get the connection string: top of the dashboard → **Connect** → under
   **Session pooler**, copy the URI. It looks like:
   `postgresql://postgres.abcdefghij:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres`
   Replace `[YOUR-PASSWORD]` with the password from step 2. Save as
   **DATABASE_URL** in your note.

   > ⚠️ Use the **Session pooler** string, NOT "Direct connection". The
   > direct host (`db.<ref>.supabase.co:5432`) is IPv6-only, and neither
   > Render's free tier nor GitHub Actions can reach IPv6. The session
   > pooler is IPv4 and behaves like a normal Postgres connection.

   > 💤 Free projects pause after ~1 week without traffic. The keep-alive
   > workflow (§5) pings the database every 3 days so this never happens.

## 2. GitHub — secrets and variables (~10 min)

You also need two free science accounts for the satellite pipeline (the spec
sheet of every variable lives in [.env.example](.env.example)):

- **NASA Earthdata** (GRACE data): register at https://urs.earthdata.nasa.gov
  → save username/password as **EARTHDATA_USER / EARTHDATA_PASS**.
- **Google Earth Engine** (Sentinel-1 + ERA5): at
  https://console.cloud.google.com create a project, enable the
  *Earth Engine API*, then **IAM & Admin → Service Accounts → Create service
  account** → after creating it, open it → **Keys → Add key → JSON**. Save:
  the account email as **EE_SERVICE_ACCOUNT**, the whole downloaded JSON
  file's text as **GEE_PRIVATE_KEY_JSON**, and the project id as
  **GEE_PROJECT**. Register the project for noncommercial Earth Engine use at
  https://code.earthengine.google.com/register.

Now in your GitHub repository: **Settings → Secrets and variables → Actions**.

On the **Secrets** tab, click **New repository secret** for each of:

| Name | Value |
|---|---|
| `DATABASE_URL` | the Session-pooler string from §1.4 |
| `EARTHDATA_USER` | NASA Earthdata username |
| `EARTHDATA_PASS` | NASA Earthdata password |
| `EE_SERVICE_ACCOUNT` | service-account email |
| `GEE_PRIVATE_KEY_JSON` | full JSON key file content |
| `GEE_PROJECT` | Google Cloud project id |
| `AQUASIGNAL_INTERNAL_API_TOKEN` | leave for §3.4 — comes from Render |
| `DISCORD_WEBHOOK_URL` | optional — Discord channel → Edit → Integrations → Webhooks |

On the **Variables** tab, click **New repository variable**:

| Name | Value |
|---|---|
| `RENDER_URL` | leave for §3.4 — e.g. `https://aquasignal-api.onrender.com` |
| `HF_REPO_ID` | your Hugging Face model repo from §7, e.g. `your-username/aquasignal-models` (the bootstrap & monthly workflows fetch the models from here) |

## 3. Render — the API (~10 min)

1. Go to **https://render.com** → **Get Started** → sign in with GitHub.
2. Dashboard → **New +** → **Blueprint** → select your repository → Render
   reads [`render.yaml`](render.yaml) and shows `aquasignal-api` → **Apply**.
3. It will ask for the `sync: false` values:
   - `AQUASIGNAL_DATABASE_URL` → the same Session-pooler string (the plain
     `postgresql://` form is fine — the backend adds its async driver itself)
   - `AQUASIGNAL_CORS_ORIGINS` → type `["http://localhost:3000"]` for now;
     you'll replace it with your Vercel URL in §4.4.
   - `HF_REPO_ID` → your Hugging Face model repo from §7, e.g.
     `your-username/aquasignal-models`. Required — the models are not in git;
     `start.sh` downloads them at boot to the paths already set in `render.yaml`.
4. After the first deploy finishes (~5 min): copy the service URL shown at
   the top (e.g. `https://aquasignal-api.onrender.com`) into the GitHub
   **variable** `RENDER_URL`. Then open the service → **Environment** → copy
   the generated value of `AQUASIGNAL_INTERNAL_API_TOKEN` into the GitHub
   **secret** of the same name.
5. Check it's alive: open `https://<your-render-url>/health` in a browser —
   you should see `"status":"ok"` ... `"db_connected":true`.

   > The schema was created automatically: every boot runs
   > `alembic upgrade head` before the API starts (see `backend/start.sh`).

## 4. Vercel — the dashboard (~5 min)

1. Go to **https://vercel.com** → **Sign Up** → continue with GitHub.
2. **Add New… → Project** → import your repository.
3. On the configure screen: set **Root Directory** to `frontend` (click
   **Edit** next to it). Framework preset should auto-detect **Vite**. Under
   **Environment Variables**, add `VITE_API_URL` = your Render URL (no
   trailing slash). Click **Deploy**.
4. Copy your new site URL (e.g. `https://aquasignal.vercel.app`) and go back
   to Render → `aquasignal-api` → **Environment** → set
   `AQUASIGNAL_CORS_ORIGINS` to `["https://aquasignal.vercel.app"]` →
   **Save changes** (the API redeploys, ~3 min).

## 5. First data load + keep-alives (~1 hour, unattended)

1. GitHub repository → **Actions** tab → if prompted, click
   **"I understand my workflows, enable them"**.
2. Left list → **Bootstrap database (run once)** → **Run workflow** →
   **Run workflow**. This applies the schema, runs the full satellite
   pipeline (30–60 min), seeds the 63 province boundaries, and clips the
   grid to the coastline. Watch it turn green. Safe to re-run if it fails.
3. Left list → **Keep free tiers awake** → **Run workflow** once to verify
   both pings pass. From now on it runs automatically: Render `/health`
   every 14 minutes, Supabase `SELECT 1` every 3 days.
4. The monthly pipeline (**Monthly pipeline** workflow) now runs by itself
   on the 5th of each month and commits the new data back to the repo —
   which automatically redeploys the API with the fresh satellite files.
   On failure it posts the log to your Discord webhook, if configured.

## 6. Verify end-to-end

1. Open your Vercel URL → **Create an account** → register with any email
   and a 12+ character password.
2. The satellite map of Vietnam loads with coloured provinces. Click one →
   the panel shows the risk score, 6-month forecast, and the satellite
   observations (GRACE, radar, rainfall…).
3. Open `https://<render-url>/health` → expect
   `{"status":"ok","db_connected":true,"models_loaded":true,...}`.
4. Cold-start behaviour: if nobody visited for >15 min and a keep-alive
   ping was missed, the first request shows a dark **"Service warming up…"**
   banner for ~30 s, then the app heals itself. That's normal on the free
   tier.

## 7. Models on Hugging Face Hub (required)

The model files are **not** in git — the full-data downscaler random forest is
~670 MB, past GitHub's 100 MB limit — so they live on the Hub and are pulled at
startup (Render) and before each scoring run (the CI workflows). You only upload
them once.

```bash
pip install -U huggingface_hub
hf auth login                              # paste a WRITE token from hf.co/settings/tokens
# Creates the repo on first upload (add --private to keep it private):
hf upload YOUR-USERNAME/aquasignal-models downscaler.pkl downscaler.pkl
hf upload YOUR-USERNAME/aquasignal-models forecaster.pt  forecaster.pt
```

Wire it up in three places, all pointing at the same `YOUR-USERNAME/aquasignal-models`:

- **Render** (§3.3): `HF_REPO_ID`, plus `HF_TOKEN` for a private repo. The
  download paths (`AQUASIGNAL_DOWNSCALER_PATH` / `AQUASIGNAL_FORECASTER_PATH` =
  `/tmp/models/...`) are already set in `render.yaml`; `start.sh` downloads the
  files before the API boots and skips the download when they're already there.
- **GitHub Actions** (§2): the `HF_REPO_ID` repository **variable** — the
  bootstrap and monthly workflows fetch the models to the repo root before
  scoring. Add `HF_TOKEN` as a repository **secret** too if the repo is private.

> Retraining the model (e.g. after a feature change) produces a new
> `downscaler.pkl` locally — re-run the two `hf upload` commands to publish it.
> Nothing in git changes.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Render deploy fails at `alembic upgrade head` | Wrong `AQUASIGNAL_DATABASE_URL` — must be the **Session pooler** string with your real password |
| `/health` shows `"db_connected":false` | Supabase paused (run the keep-alive workflow) or wrong password |
| Browser console shows CORS errors | `AQUASIGNAL_CORS_ORIGINS` must be a JSON list containing your exact Vercel origin, e.g. `["https://aquasignal.vercel.app"]` |
| Map loads but provinces are grey | Bootstrap workflow hasn't completed — check the Actions tab |
| "Service warming up…" never clears | Render service crashed — check its **Logs** tab in the Render dashboard |
| `/health` shows `"models_loaded":false` | `HF_REPO_ID` not set on Render (§3.3/§7), or the HF repo/file names don't match — the API still serves cached scores, but it's a sign the models didn't download |
| Bootstrap/monthly run fails with `FileNotFoundError: downscaler.pkl` | The `HF_REPO_ID` repository **variable** is missing (§2/§7) — the workflow couldn't fetch the models before scoring |
| Monthly run fails with Earthdata 401 | Re-check `EARTHDATA_USER`/`EARTHDATA_PASS`; log attached in the Discord message |
