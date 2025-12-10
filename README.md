📚 AI-Powered Library Management System

Smart book search, similarity-based recommendations, and full library CRUD

This project is an intelligent Library Management System built with Flask, SQLite, and AI embeddings for book similarity and personalized recommendations.
It supports user accounts, an admin panel, responsive UI, and advanced semantic search powered by vector embeddings.

🚀 Features

🔍 AI Semantic Book Search

Converts book titles, descriptions, or summaries into vector embeddings.

Supports semantic queries (e.g., “books about wizards and adventure”).

Uses cosine similarity to return the closest matching books.

📖 Smart Recommendation Engine

Recommends books related to the one currently viewed.

Automatically shows “You May Also Like” suggestions based on embeddings.

🛡️ User System

User registration/login

Secure password hashing

Profile with reading history

🛠️ Admin Panel

Add, edit, delete books

Upload covers, descriptions, genres, authors

Generate embeddings automatically

🖼️ Responsive UI

Sidebar navigation

Search bar

Grid book listings

Works on both PC and mobile

🧠 How the AI Works
1. Book Embeddings

Each book has:

title

description

genre

author

These fields are combined and passed to an embedding model (Gemini Embeddings, OpenAI, or SentenceTransformers).

Example vector generation:

embedding = embed_model.embed_text(f"{title}. {description}. {genre}. {author}")

2. Similarity Search

When searching or viewing a book:

similarity = cosine_similarity(query_vector, book_vector)


The top results are returned as:

Recommended books

Search results

Related reading list


⚙️ Installation & Setup
1. Clone Repository
git clone https://github.com/berghouti/Library-management.git
cd LibraryAI

2. Create Virtual Environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/Mac

3. Install Dependencies
pip install -r requirements.txt

4. Configure Embedding Provider

In .env:

EMBEDDING_API_KEY=your_key
EMBEDDING_MODEL=your_model_name
SECRET_KEY=your_flask_secret


Supported models:

google-apis/gemini-embedding

text-embedding-3-small

sentence-transformers

5. Initialize Database
python setup_db.py   # if included

6. Run App
flask run

🧩 Example: Adding a Book with Embeddings
from embeddings import embed_text

text = f"{title}. {description}. {genre}. {author}"
vector = embed_text(text)

cursor.execute("""
    INSERT INTO books (title, description, genre, author, embedding)
    VALUES (?, ?, ?, ?, ?)
""", (title, description, genre, author, json.dumps(vector)))

🎯 Search Example
query_vec = embed_text(user_query)
results = rank_by_cosine_similarity(query_vec, all_books)

📌 Future Enhancements

User-based collaborative filtering

Rating system

Book borrowing module

Vector database integration (Milvus / Pinecone)

Chatbot librarian assistant
