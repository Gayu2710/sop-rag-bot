import streamlit as st
import chromadb
from groq import Groq
import time
import docx

# Page config
st.set_page_config(page_title="SOP Assistant", page_icon="🤖", layout="wide")

# Initialize
@st.cache_resource
def init_chatbot():
    try:
        groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        client = chromadb.PersistentClient(path="./chromadb")
        collection = client.get_or_create_collection("sop_chunks")
        return groq_client, collection, client
    except Exception as e:
        st.error(f"Initialization error: {e}")
        return None, None, None

groq_client, collection, client = init_chatbot()

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks

def process_docx(file):
    """Extract text from DOCX including tables"""
    doc = docx.Document(file)
    full_text = []
    
    for element in doc.element.body:
        if element.tag.endswith('p'):
            para = docx.text.paragraph.Paragraph(element, doc)
            if para.text.strip():
                full_text.append(para.text)
        elif element.tag.endswith('tbl'):
            table = docx.table.Table(element, doc)
            for row in table.rows:
                row_text = ' | '.join([cell.text.strip() for cell in row.cells])
                if row_text.strip():
                    full_text.append(row_text)
    
    return "\n".join(full_text)

def answer_sop(question):
    start = time.time()
    results = collection.query(query_texts=[question], n_results=5)
    docs = results["documents"][0]
    ids = results["ids"][0]
    
    context = "\n\n---\n\n".join(docs)
    
    prompt = f"""You are an SOP assistant. Use ONLY the SOP context below to answer the question.
If the answer is not in the SOP, say you cannot find it in the SOP.

SOP context:
{context}

Question: {question}

Answer:"""
    
    chat = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    
    latency = int((time.time() - start) * 1000)
    return chat.choices[0].message.content, ids[0], latency

# Main UI
st.title("🤖 Incident Management SOP Assistant")

# Check if database is empty
if collection.count() == 0:
    st.warning("⚠️ First-time setup required: Upload your SOP document to get started")
    
    uploaded_file = st.file_uploader("Upload SOP Document (DOCX)", type=['docx'])
    
    if uploaded_file:
        with st.spinner("Processing document..."):
            try:
                # Extract text
                raw_text = process_docx(uploaded_file)
                st.success(f"✅ Extracted {len(raw_text)} characters")
                
                # Chunk text
                chunks = chunk_text(raw_text)
                st.info(f"📝 Created {len(chunks)} chunks")
                
                # Store in ChromaDB
                ids = [f"chunk-{i}" for i in range(len(chunks))]
                metas = [{"index": i} for i in range(len(chunks))]
                collection.upsert(ids=ids, documents=chunks, metadatas=metas)
                
                st.success(f"🎉 Successfully indexed {len(chunks)} chunks! Refresh the page to start chatting.")
                st.balloons()
                
            except Exception as e:
                st.error(f"Error processing document: {e}")
else:
    st.markdown(f"**Database Status:** {collection.count()} chunks indexed | Ready to answer questions")
    
    # Sidebar
    with st.sidebar:
        st.header("📚 Example Questions")
        st.markdown("""
        - What are the severity levels?
        - What is the update cadence for Sev2 incidents?
        - How do we handle NodeNotReady incidents?
        - What tools are used for incident detection?
        - What should be documented when logging an incident?
        """)
        
        st.divider()
        st.markdown("**Tech Stack:**")
        st.markdown("- ChromaDB (Vector Store)")
        st.markdown("- Groq Llama-3.3-70b")
        st.markdown("- Streamlit UI")
        
        if st.button("🔄 Reset Database"):
            client.delete_collection("sop_chunks")
            st.success("Database reset! Refresh to re-upload.")
    
    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "metadata" in message:
                st.caption(f"Source: {message['metadata']['source']} | Latency: {message['metadata']['latency']}ms")
    
    if prompt := st.chat_input("Ask about incidents, severity levels, procedures..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Searching SOP..."):
                response, source, latency = answer_sop(prompt)
                st.markdown(response)
                st.caption(f"Source: {source} | Latency: {latency}ms")
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response,
            "metadata": {"source": source, "latency": latency}
        })

