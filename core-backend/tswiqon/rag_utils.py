import os
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings # More direct than via LiteLLM for this
from langchain.vectorstores import FAISS
import logging

# Configure basic logging for RAG utils
logging.basicConfig(level=logging.INFO, format='[RAGUtils] %(asctime)s - %(levelname)s - %(message)s')

KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge_base')
FAISS_INDEX_PATH = os.path.join(os.path.dirname(__file__), 'faiss_index')
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # A good default sentence transformer

def create_and_save_faiss_index():
    if os.path.exists(FAISS_INDEX_PATH):
        logging.info(f"FAISS index already exists at {FAISS_INDEX_PATH}. Skipping creation.")
        return FAISS.load_local(FAISS_INDEX_PATH, HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME), allow_dangerous_deserialization=True)

    if not os.path.exists(KNOWLEDGE_BASE_DIR) or not os.listdir(KNOWLEDGE_BASE_DIR):
        logging.warning(f"Knowledge base directory {KNOWLEDGE_BASE_DIR} is empty or does not exist. Cannot create FAISS index.")
        return None

    logging.info(f"Loading documents from {KNOWLEDGE_BASE_DIR}...")
    loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="*.txt", loader_cls=TextLoader, loader_kwargs={'autodetect_encoding': True})
    documents = loader.load()

    if not documents:
        logging.warning("No documents loaded from the knowledge base. FAISS index will be empty.")
        return None

    logging.info(f"Loaded {len(documents)} documents. Splitting into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    texts = text_splitter.split_documents(documents)
    
    logging.info(f"Split into {len(texts)} text chunks. Generating embeddings using '{EMBEDDING_MODEL_NAME}'...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    
    logging.info("Creating FAISS index from text chunks...")
    vector_store = FAISS.from_documents(texts, embeddings)
    
    logging.info(f"Saving FAISS index to {FAISS_INDEX_PATH}...")
    vector_store.save_local(FAISS_INDEX_PATH)
    logging.info("FAISS index created and saved successfully.")
    return vector_store

def query_vector_store(query: str, k: int = 3) -> list[str]:
    logging.info(f"Attempting to query vector store with query: '{query}' for top {k} results.")
    if not os.path.exists(FAISS_INDEX_PATH):
        logging.error(f"FAISS index not found at {FAISS_INDEX_PATH}. Please create it first.")
        # Attempt to create it on the fly if not found
        vector_store = create_and_save_faiss_index()
        if not vector_store:
            return ["Error: FAISS index not found and could not be created."]
    else:
        try:
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
            vector_store = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
            logging.info("FAISS index loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading FAISS index: {e}. Trying to rebuild...")
            # If loading fails, try rebuilding it
            vector_store = create_and_save_faiss_index()
            if not vector_store:
                 return [f"Error: FAISS index could not be loaded or rebuilt: {e}"]


    if vector_store:
        try:
            retrieved_docs = vector_store.similarity_search(query, k=k)
            logging.info(f"Retrieved {len(retrieved_docs)} documents.")
            return [doc.page_content for doc in retrieved_docs]
        except Exception as e:
            logging.error(f"Error during similarity search: {e}")
            return [f"Error during similarity search: {e}"]
    else:
        return ["Error: Vector store is not available."]