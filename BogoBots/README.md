# BogoBots

BogoInsight is an LLM agent (bot) project, aiming to explore the capabilities and usages of agents built upon large language models (LLMs).

This project is bulit upon Streamlit and LangChain.

## To-do list

- [ ] Auto-cleansing of uploaded/generated files
- [ ] Update model versions

## File structure

- `.streamlit/` streamlit configs
- `callbacks/` LangChain callback handlers
- `configs/` configurations
- `document_loaders/` LangChain document loaders
- `graphs/` LangChain graphs
- `pages/` Streamlit pages
- `parsers/` LangChain parsers
- `scripts/` indivisual scripts
- `tools/` LangChain tools
- `utils/` utility functions
- `app.js` Node.js proxy for Streamlit app, a workaround for publishing on cPanel
- `BogoBots.py` entrypoint for Streamlit app
- `loader.cjs` cPanel Node.js entrypoint
- `run.sh` entrypoint for production

## Usage

### Individual scripts

Should be run under this root dir.

```cmd
python scripts/add_booknotes_to_vectorstore.py --file_path=./data/booknotes/haodang2000.txt --book_name="浩荡两千年：中国企业公元前7世纪~1869年"
```

### Local development

Windows not supported, because pymilvus requires running on Unix.

```cmd
streamlit run BogoBots.py
```

### Docker development

Run without rebuild:

```cmd
docker-compose up
```

Run with rebuild:

```cmd
docker-compose up --build
```

### Production

```cmd
bash run.sh
```

### Clean docker WSL

```cmd
wsl --shutdown
diskpart
select vdisk file="C:\Users\neils\AppData\Local\Docker\wsl\data\ext4.vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
```