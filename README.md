Absolutely — here is a clean, professional **README.md** tailored exactly to your project structure and workflow. You can paste this directly into your repo.

---

# 📘 **Reference Extraction Pipeline**

### *PDF → DSPy Parsing → OpenAlex Matching → Structured Excel Output*

This project extracts **paper titles**, **first/last author names**, **affiliations**, and **emails** from academic references stored in PDF files.
It uses a hybrid pipeline combining:

* **Llama 3 70B Instruct Model/Llama 4 Maverick** (via HuggingFace Inference API or Ollama)
* **DSPy** for structured parsing, work-type inference, and match ranking
* **OpenAlex API** for authoritative metadata
* **Custom logic + fallback rules** for robust extraction
* **Excel output** (via `openpyxl`)

---

# 📁 Project Structure

```
project-root/
│
├── config.py
├── dspy_models.py   
├── openalex_client.py 
├── pdf_utils.py 
├── pipeline.py
├── main.py
│
├── References.pdf
└── output.xlsx
```

---

# 🔧 Installation

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install required packages

```bash
pip install -r requirements.txt
```

---

# 🔐 API Keys/Setting Up Models

Set your HuggingFace API key for the LLM model and openalex API email address in config.py

OR download local models via ollama and initialise the models by editing config.py and dspy_models.py accordingly.

```bash
ollama pull llama4:maverick
```

---

# ▶️ Running the Pipeline

```bash
python main.py --pdf References.pdf --out output.xlsx
```

Optional: limit number of processed references (debugging):

```bash
python main.py --pdf References.pdf --out output.xlsx --max_refs 10
```

---

# 🧠 How It Works

### **1. PDF Extraction**

`pdf_utils.py` extracts raw text and splits it into individual references.

### **2. DSPy Parsing**

`dspy_models.py` uses Llama 4 to:

* Extract title
* Extract year
* Extract author list
* Extract emails
* Infer work type (“book”, “journal-article”, etc.)

### **3. OpenAlex Candidate Retrieval**

`openalex_client.py` performs:

* Stage 1: precise `title.search` query
* Stage 2: fallback broad keyword search with year window

### **4. DSPy Matching**

`ChooseOpenAlexMatch` signature performs:

* Title similarity ranking
* Author surname overlap
* Year proximity
* Type consistency
* Strict rejection of irrelevant works
* Returns best OpenAlex ID + reasoning

### **5. Final Assembly**

`pipeline.py` builds:

* First/last author info
* Affiliations
* Emails
* DSPy rationale
* Fallbacks to avoid empty rows

And writes everything to Excel.

---

# 📊 Output Format (Excel Columns)

| Column                    | Description                            |
| ------------------------- | -------------------------------------- |
| paper_title               | Parsed or fallback title               |
| year                      | Publication year                       |
| first_author_name         | First author name (OpenAlex or parsed) |
| first_author_affiliations | Clean semicolon-separated list         |
| first_author_emails       | Emails from reference text             |
| last_author_name          | Last author name                       |
| last_author_affiliations  | Clean affiliations                     |
| last_author_emails        | Usually empty (rare in refs)           |
| reference_raw             | Original reference text                |
| notes                     | DSPy chain of thought + match info     |

---

# 🧪 Testing

Try with a small number of references first:

```bash
python main.py --pdf References.pdf --out test_output.xlsx --max_refs 5
```

---

# 🎯 Future Improvements (Optional)

* Add **Streamlit UI**
* Add **local caching** of OpenAlex responses (huge speedup)
* Use **DSPy BootstrapFewShot** to auto-improve ranking
* Add **unit tests** for parsing and filtering
* Package project as a pip module

---

# 🙌 Credits

* **DSPy** by Stanford NLP
* **OpenAlex** for scholarly metadata
* **Meta Llama 4 models** via Hugging Face Inference API

---


