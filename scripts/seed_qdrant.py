import os
from pathlib import Path
from dotenv import load_dotenv

# Disable HuggingFace tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

# Define paths based on the project structure
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
KB_DIR = PROJECT_ROOT / "knowledge_base"
ENV_PATH = PROJECT_ROOT / "backend" / ".env"

# Load environment variables from backend/.env
load_dotenv(dotenv_path=ENV_PATH)

# Fetch Qdrant Cloud settings from environment
QDRANT_URL = os.getenv("QDRANT_HOST") or os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "dental_knowledge")


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

    print(f"🚀 4. Uploading chunks to Qdrant Cloud ({COLLECTION_NAME})...")
    QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        collection_name=COLLECTION_NAME,
        force_recreate=True
    )
    
    print("\n🎉 Knowledge Base successfully embedded and saved to Qdrant Cloud!")

if __name__ == "__main__":
    try:
        seed_vector_db()
    except Exception as e:
        print(f"🚨 An error occurred: {e}")