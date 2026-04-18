# DMRB Legacy — AI Agent (OpenAI)

See also: [OPERATIONAL_AI_AGENT.md](OPERATIONAL_AI_AGENT.md) for product behavior spec and refusal policy.

The **DMRB AI Agent** screen (`ui/screens/ai_agent.py`) calls OpenAI Chat Completions from the Streamlit process for local testing.

Long-term, the product target is **FastAPI enqueue + worker + LLM** (see `docs/DMRB_master_blueprint.md`). This Legacy path is intentional until that pipeline exists.

## Where to put your API key

Use **one** of these (not both required — pick what fits your setup):

| Method | Where |
|--------|--------|
| **Environment variable** | Export `OPENAI_API_KEY` in the shell (or your IDE/run config) **before** `streamlit run app.py`. |
| **Streamlit secrets file** | Edit **`dmrb/dmrb-legacy/.streamlit/secrets.toml`** — `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL` are already there; paste your key into the empty `OPENAI_API_KEY` string. Template for new setups: [`.streamlit/secrets.toml.example`](../../.streamlit/secrets.toml.example). |

**Precedence:** If both are set, the **environment variable wins** over `secrets.toml` (see `config/settings.py` → `get_setting`).

After changing `secrets.toml`, **restart** the Streamlit server so the key is picked up.

Keep real keys out of git; ensure `.streamlit/secrets.toml` stays ignored or use a local-only copy.

## Example lines (already in your `secrets.toml`)

```toml
OPENAI_API_KEY = ""
OPENAI_CHAT_MODEL = "gpt-4o-mini"
```

Put your key inside the quotes, e.g. `OPENAI_API_KEY = "sk-..."`. Default model if you remove `OPENAI_CHAT_MODEL`: `gpt-4o-mini` (see `config/settings.py`).

## Run

```bash
cd dmrb/dmrb-legacy
python -m pip install -r requirements.txt
streamlit run app.py
```

Use the **same Python environment** for `pip` and `streamlit` (e.g. activate the repo venv first: `source ../../.venv/bin/activate` from `dmrb/dmrb-legacy` if your venv lives at the repo root).

Open the sidebar **DMRB AI Agent** and send a message.

## `ModuleNotFoundError: No module named 'openai'`

The interpreter running Streamlit does not have the `openai` package. Install into **that** environment, for example:

```bash
cd dmrb/dmrb-legacy
../../.venv/bin/python -m pip install -r requirements.txt
../../.venv/bin/streamlit run app.py
```

(Adjust the path if your virtualenv is elsewhere.)

## Missing key

If the key is not set, the UI shows instructions pointing at this file.
