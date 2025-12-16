import streamlit as st
import chromadb
from groq import Groq
import time

# Page config
st.set_page_config(page_title="SOP Assistant", page_icon="🤖", layout="wide")

# Initialize
@st.cache_resource
def init_chatbot():
    try:
        groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        client = chromadb.PersistentClient(path="./chromadb")
        collection = client.get_or_create_collection("sop_chunks")
        return groq_client, collection
    except Exception as e:
        st.error(f"Initialization error: {e}")
        return None, None

groq_client, collection = init_chatbot()

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

# UI
st.title("🤖 Incident Management SOP Assistant")
st.markdown("Ask questions about Kubernetes incident management procedures powered by RAG.")

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

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "metadata" in message:
            st.caption(f"Source: {message['metadata']['source']} | Latency: {message['metadata']['latency']}ms")

# Chat input
if prompt := st.chat_input("Ask about incidents, severity levels, procedures..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get bot response
    with st.chat_message("assistant"):
        with st.spinner("Searching SOP..."):
            response, source, latency = answer_sop(prompt)
            st.markdown(response)
            st.caption(f"Source: {source} | Latency: {latency}ms")
    
    # Add assistant message
    st.session_state.messages.append({
        "role": "assistant", 
        "content": response,
        "metadata": {"source": source, "latency": latency}
    })
