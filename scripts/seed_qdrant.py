import os
from pathlib import Path

# Disable HuggingFace tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

# Define paths based on the project structure
CURRENT_DIR = Path(__file__).resolve().parent
KB_DIR = CURRENT_DIR.parent / "knowledge_base"

# Qdrant Database URL
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "clinic_knowledge"

def seed_vector_db():
    print("🧠 1. Loading AI Embedding Model (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print(f"📂 2. Reading Markdown files from {KB_DIR}...")
    loader = DirectoryLoader(str(KB_DIR), glob="**/*.md", loader_cls=TextLoader)
    docs = loader.load()
    print(f"   -> Found {len(docs)} files.")

    print("✂️ 3. Splitting text into chunks...")
    text_splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    print(f"   -> Created {len(chunks)} chunks.")

    print("🚀 4. Uploading chunks to Qdrant Vector Database...")
    QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        url=QDRANT_URL,
        collection_name=COLLECTION_NAME,
        force_recreate=True
    )
    
    print("\n🎉 Knowledge Base successfully embedded and saved to Qdrant!")

if __name__ == "__main__":
    try:
        seed_vector_db()
    except Exception as e:
        print(f"🚨 An error occurred: {e}")