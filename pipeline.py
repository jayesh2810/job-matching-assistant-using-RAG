# !pip install -qqq langchain_openai
# !pip install -qqq -U langchain-community
# !pip install -qqq -U langchain_chroma
# !pip install -qqq -U langchain-huggingface
# !pip install -qqq -U datasets

from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from datasets import load_dataset

# Load the dataset
dataset = load_dataset("cnamuangtoun/resume-job-description-fit")

# dataset.column_names

# type(dataset)

# dataset['train'][0]

# print(len(dataset['train']))
# print(len(dataset['test']))

db_name = "job_embeddings_db"
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en",encode_kwargs={'normalize_embeddings':True})

import os

if os.path.exists(db_name):
  Chroma(persist_directory = db_name,embedding_function = embeddings).delete_collection()

# Initialize the Chroma vector store
vector_store = Chroma(persist_directory=db_name, embedding_function=embeddings)

# Fetch and store embeddings
for record in dataset['train']:
    resume_text = record['resume_text']
    job_description_text = record['job_description_text']

    # Generate embeddings for resume and job description
    resume_embedding = embeddings.embed_query(resume_text)
    job_description_embedding = embeddings.embed_query(job_description_text)

    # Store embeddings in the vector store with metadata
    vector_store.add_texts(
        texts=[resume_text, job_description_text],
        metadatas=[{'type': 'resume'}, {'type': 'job_description'}]
    )

# Persist the vector store
# vector_store.persist()

# embedding_sample = embeddings.embed_query("This is a sample text.")
# print(len(embedding_sample))


from langchain_openai import ChatOpenAI

from google.colab import userdata
openai_api = userdata.get('OPENAI_API_KEY')

llm = ChatOpenAI(api_key=openai_api)

retriever = vector_store.as_retriever()

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder

prompt_search_query = ChatPromptTemplate.from_messages([
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    ("user", "Based on the above conversation, generate a structured search query to find relevant job postings. "
             "Ensure the query includes key skills, experience level, and location from the user's request.")
])

from langchain.chains import create_history_aware_retriever

retriever_chain = create_history_aware_retriever(llm, retriever, prompt_search_query)

prompt_get_answer = ChatPromptTemplate.from_messages([
    ("system", "You are an AI-powered recruitment assistant. Your goal is to provide job recommendations "
               "based on the user's skills, experience, and location. Use the following job postings "
               "to generate a professional and structured response. Do not return context and system messages.\n\n"
               "{context}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])

from langchain.chains.combine_documents import create_stuff_documents_chain
document_chain=create_stuff_documents_chain(llm,prompt_get_answer)

from langchain.chains import create_retrieval_chain
retrieval_chain = create_retrieval_chain(retriever_chain, document_chain)

from langchain_core.messages import HumanMessage, AIMessage

chat_history = []
response = retrieval_chain.invoke({
"chat_history":chat_history,
"input":"I am skilled in Machine learning and Data science with 3 years of experience. Looking for a job in San Francisco Location. Can you provide me some options?"
})
print(response["answer"])

response2 = retrieval_chain.invoke({
"chat_history":chat_history,
"input":"I am skilled in Java and Python with 8 years of experience. Looking for a job in Mumbai Location. Can you provide me some options?"
})
print(response2["answer"])

from langchain_core.messages import HumanMessage, AIMessage

def chat(question, history):
    ai_message = retrieval_chain.invoke({"input": question, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=question), ai_message["answer"]])
    return ai_message['answer']

import gradio as gr

gradio_interface = gr.ChatInterface(chat).launch()

