# Deploy on Vercel + Hugging Face Space

This guide deploys:

- `frontend/` to `Vercel`
- `backend/` to a `Hugging Face Docker Space`

This is the cleanest zero-cost public demo setup for this repo.

## Before you start

You need:

- a GitHub account
- a Vercel account
- a Hugging Face account

Important limitation:

- Free Hugging Face CPU Spaces can run the backend and text-answer flow.
- Audio transcription needs a GPU-backed backend, so for a free CPU Space you should disable audio input in the Vercel frontend.

## Part 1: Push your repo to GitHub

1. Create a GitHub repository.
2. Push this project to GitHub.
3. Confirm the repo contains:
   - `frontend/`
   - `backend/`
   - `Dockerfile`

## Part 2: Deploy the backend to Hugging Face Space

### Create the Space

1. Open [https://huggingface.co/new-space](https://huggingface.co/new-space).
2. Choose a Space name.
3. Set visibility to `Public`.
4. Choose `Docker` as the SDK.
5. Create the Space.

### Add your project files

You have two easy options:

#### Option A: Upload from the Hugging Face web UI

1. Open the new Space repository page.
2. Use `Files` -> `Add file` -> `Upload files`.
3. Upload the project files from this repo.
4. Make sure the root of the Space contains `Dockerfile`, `backend/`, and `requirements.txt`.

#### Option B: Push with git

1. Clone the Space repo locally.
2. Copy this project into that repo.
3. Commit and push to Hugging Face.

### Configure Space variables

In the Hugging Face Space, open `Settings` and add these variables if needed:

- `APP_STAGE=production`
- `STORAGE_DIR=/tmp/ascent-storage`
- `HF_TOKEN=...` only if you want Hugging Face hosted LLM calls that require it
- `MONGODB_URL=...` only if you want external Mongo persistence
- `MONGODB_DB=ai_interview_sim` optional

Notes:

- This repo already falls back to flat-file mode if `MONGODB_URL` is missing.
- On free Spaces, local disk is not persistent across restarts.
- For resume/demo use, flat-file mode is fine.

### Wait for the build

1. After upload or push, Hugging Face will build the Docker image automatically.
2. Watch the build logs.
3. When the Space becomes `Running`, open:

```text
https://YOUR_SPACE_NAME.hf.space/api/health
```

Expected result:

- JSON with `status: ok`
- `gpu: unavailable` on free CPU hardware
- `audio_transcribe: disabled (GPU required)` on free CPU hardware

### Copy your backend base URL

Your frontend will use:

```text
https://YOUR_SPACE_NAME.hf.space/api
```

## Part 3: Deploy the frontend to Vercel

### Import the GitHub repo

1. Open [https://vercel.com/new](https://vercel.com/new).
2. Import your GitHub repository.
3. Set the `Root Directory` to `frontend`.

### Configure build settings

Use these values:

- Framework Preset: `Vite`
- Build Command: `npm run build`
- Output Directory: `dist`

### Add environment variables

In the Vercel project settings, add:

```text
VITE_API_BASE=https://YOUR_SPACE_NAME.hf.space/api
VITE_ENABLE_AUDIO_INPUT=false
VITE_AUDIO_INPUT_HINT=This public demo uses a free CPU backend, so text answers are enabled and audio answers are disabled.
```

Why disable audio?

- The free Hugging Face CPU Space can host the backend well enough for a resume demo.
- Whisper audio transcription in this project expects a GPU-backed backend.
- Hiding the audio tab makes the public deployment feel intentional instead of broken.

### Deploy

1. Click `Deploy`.
2. Wait for the Vercel build to finish.
3. Open the Vercel URL.

## Part 4: Test the public app

Test these flows:

1. Open the Vercel site.
2. Start a session.
3. Upload a resume PDF.
4. Complete setup.
5. Start the interview.
6. Submit text answers.
7. Finish the interview and verify the final report loads.

Also verify:

- camera permission works
- posture monitoring works
- backend requests succeed
- no CORS issues appear

## Part 5: Add this to your resume

Use wording like:

- `Deployed a multimodal AI interview simulator with a Vercel frontend and Hugging Face Space backend`
- `Built a public demo with resume parsing, semantic scoring, posture monitoring, and interview analytics`
- `Designed a zero-cost portfolio deployment architecture for an ML-backed web application`

## Recommended setup

For your current repo, I recommend:

- `Vercel` for the frontend
- `Hugging Face Space` for the backend
- `MongoDB Atlas Free` only if you want persistent session and report storage

## If you want audio enabled later

You have three paths:

1. Move the backend to a GPU host.
2. Add a lighter ASR path for CPU hosting.
3. Use browser-based speech-to-text for the public demo while keeping server scoring.

## Troubleshooting

### Vercel frontend loads but API calls fail

Check:

- `VITE_API_BASE` ends with `/api`
- the Hugging Face Space is public
- the Space is currently awake and healthy

### Hugging Face build fails

Check:

- `Dockerfile` is at the repo root in the Space
- `requirements.txt` exists
- the upload preserved the `backend/` folder structure

### Resume upload or reports disappear later

That is expected on free Space restarts if you are using local storage only.

If you want persistence, connect MongoDB Atlas free tier for metadata and reports.

### Audio answer does not work

That is expected on a free CPU Space with the current backend.

Use text mode, or move audio transcription to GPU-backed hosting.
