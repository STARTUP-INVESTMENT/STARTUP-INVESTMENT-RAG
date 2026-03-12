import os
from pathlib import Path
import PyPDF2
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# --- 설정 ---
PDF_DIR = "./docs"
EMBEDDING_DIM = 1024
INDEX_FILE = "faiss.index"
METADATA_FILE = "metadata.pkl"

# --- 전역 변수 ---
index = faiss.IndexFlatL2(EMBEDDING_DIM)
metadata = []
model = SentenceTransformer("intfloat/multilingual-e5-large-instruct")

# --- PDF 읽기 ---
def read_pdf(file_path: str) -> str:
    reader = PyPDF2.PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()

def insert_pdf(file_path: str):
    content = read_pdf(file_path)
    if not content:
        print(f"{file_path} is empty or unreadable.")
        return
    vector = model.encode(content, convert_to_numpy=True).astype("float32")
    index.add(np.array([vector]))
    metadata.append({"filename": file_path, "content": content})
    print(f"Inserted {file_path} into FAISS index.")

def insert_all_pdfs(directory: str):
    pdf_paths = Path(directory).glob("*.pdf")
    for pdf_path in pdf_paths:
        insert_pdf(str(pdf_path))

def save_index(index_path=INDEX_FILE, metadata_path=METADATA_FILE):
    faiss.write_index(index, index_path)
    with open(metadata_path, "wb") as f:
        pickle.dump(metadata, f)
    print("Index and metadata saved.")

def load_index(index_path=INDEX_FILE, metadata_path=METADATA_FILE):
    global index, metadata
    if Path(index_path).exists() and Path(metadata_path).exists():
        index = faiss.read_index(index_path)
        with open(metadata_path, "rb") as f:
            metadata = pickle.load(f)
        print("FAISS index and metadata loaded")
    else:
        print("No index found, starting new one.")

# --- FastAPI 서버 ---
app = FastAPI()

class SearchRequest(BaseModel):
    text: str
    top_k: int = 5

@app.post("/search")
def search(req: SearchRequest):
    if not metadata or index is None:
        return {"results": []}
    q_vec = model.encode(req.text, convert_to_numpy=True).astype("float32")
    D, I = index.search(np.array([q_vec]), req.top_k)
    results = []
    for idx in I[0]:
        if idx == -1 or idx >= len(metadata):
            continue
        results.append(metadata[idx])
    return {"results": results}

# --- 메인 실행 ---
if __name__ == "__main__":
    load_index()
    insert_all_pdfs(PDF_DIR)
    save_index()
    print("Starting FAISS server on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)