# Private Seedance 2.5 Omni Reference App

This is a small private starter app for reference-driven video generation.

## What it does

- Upload image, video, and audio references
- Enter a prompt
- Choose duration from 4 to 30 seconds
- Choose resolution and aspect ratio
- Optionally run the prompt through GPT-6 first
- Submit to a configurable Seedance provider adapter
- Review recent jobs in the UI

## Important limitation

This is a working private starter app, but the real generation step depends on your actual Seedance access path.

Different providers expose Seedance 2.5 through different APIs. Because of that, you will likely need to adjust the `submit_seedance_job()` function in `app.py` to match the exact provider request format.

## Run locally

```bash
cd seedance_omni_app
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Environment variables

### Optional prompt cleanup through GPT-6

```bash
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-6
```

### Seedance provider adapter

```bash
SEEDANCE_API_URL=https://your-provider.example/api/generate
SEEDANCE_API_KEY=your_provider_key
SEEDANCE_API_AUTH_HEADER=Authorization
SEEDANCE_API_AUTH_PREFIX=Bearer
```

If you do not set the Seedance provider variables, the app still works in mock mode and lets you test the interface and prompt cleanup flow.

## Files

- `app.py` main FastAPI app
- `templates/index.html` UI
- `static/app.js` frontend logic
- `static/styles.css` styles
- `jobs.json` saved job history after first use

## Privacy

- This starter is private by default
- No public deployment is included
- Keep API keys on the server side only
