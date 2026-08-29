# WE (Telecom Egypt) Intelligent Customer-Support Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers customer questions
grounded in the official [te.eg](https://te.eg) website, with support for
customer-uploaded documents (PDF, DOCX, TXT, HTML, images). Built as a
proof-of-concept case study.

## Features

- Scrapes and indexes Telecom Egypt service pages into a persistent vector
  store (currently covers the **Entertainment** category)
- Answers in Arabic, English, or Egyptian dialect — matching the customer's
  language
- Lets customers upload their own PDF / DOCX / TXT / HTML / image files and
  ask questions about them
- Grounded, bounded answers only — never invents prices, USSD codes, or
  details not in the retrieved context; falls back to "contact 155" when
  unsure
- Cites the source URL or filename behind every factual claim
- Branded Gradio chat interface with an animated avatar (idle / thinking /
  talking / confused states)
- Runs anywhere — local machine, VM, or Docker container (no Colab
  dependency)

## Project structure

```
.
├── scraper.py          # te.eg scraping: discover, extract, clean, chunk
├── Document_loader.py  # multi-format upload handling (PDF/DOCX/TXT/HTML/Image)
├── vector_store.py     # embeddings + persistent ChromaDB collection
├── rag.py              # query normalization, retrieval, Gemini answer generation
├── ingest.py           # one-shot / periodic script to (re)build the knowledge base
├── app.py              # standalone Gradio chat interface
├── requirements.txt    # Python dependencies
└── avatar_frames/      # base.png, thinking.png, talking.png, confused.png
```

## Setup

### 1. Clone and install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your API key

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_gemini_api_key_here
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey) if you
don't have one. `rag.py` loads this automatically via `python-dotenv` — never
commit your `.env` file.

### 3. Build the knowledge base

Run once (and again whenever the site content changes):

```bash
python ingest.py
```

This scrapes every category listed in `ingest.py`'s `CATEGORIES` dict,
chunks the content, embeds it, and stores it in a persistent ChromaDB
collection under `./chroma_db`. To add more categories, uncomment or add
entries in `CATEGORIES`.

### 4. Add avatar images (optional)

Place `base.png`, `thinking.png`, `talking.png`, and `confused.png` inside
`avatar_frames/`. The app runs fine without them — it falls back to
`base.png` for any missing state.

### 5. Run the app

```bash
python app.py
```

Open the URL Gradio prints (defaults to `http://0.0.0.0:7860`).

## How it works

1. **Scrape** — `scraper.py` discovers every sub-service link on a category
   page, extracts clean text, strips repeated nav/footer boilerplate, and
   splits it into ~500-character chunks.
2. **Embed & store** — `vector_store.py` embeds chunks with a multilingual
   sentence-transformer model and upserts them into a persistent ChromaDB
   collection (cosine similarity), tagged with `url`, `category`, and
   `source_type`.
3. **Upload** — `Document_loader.py` extracts text from a customer's file
   (using Gemini's multimodal API for images, no local OCR needed) and
   chunks it with the same logic, tagged `source_type="user_upload"`.
4. **Answer** — `rag.py` normalizes the customer's query with Gemini,
   retrieves the closest chunks, drops anything below a relevance threshold
   (cosine distance ≤ 0.55), and asks Gemini to answer strictly from what's
   left — citing sources and replying in the customer's language.
5. **Interface** — `app.py` serves a purple-branded Gradio chat app with an
   avatar that visibly thinks, talks, and shows confusion on a fallback
   answer.

## Notes

- Currently scoped to the **Entertainment** category; teammates are covering
  the remaining categories (mobile, internet, landline, roaming, number
  portability, etc.) — add their category URLs to `ingest.py`.
- For production/on-prem deployment, containerize `app.py` and schedule
  `ingest.py` to run periodically so the knowledge base stays current with
  site changes.

  that's a video of the bot : https://drive.google.com/drive/folders/128hLJIfhzlxcnfTX3yadMtPyVID_cQNe?dmr=1&ec=wgc-drive-%5Bmodule%5D-goto
