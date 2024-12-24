import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import pickle
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.url_map.strict_slashes = False

current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
conn = sqlite3.connect('database.db')
query = """
SELECT idB, title, description, author, categories
FROM books
"""
books_df = pd.read_sql(query, conn)

def query_db(query, args=(), one=False):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute(query, args)
        con.commit()

def is_valid_sql(sql_query):
    destructive_keywords = ["drop", "delete", "truncate", "alter"]
    return not any(keyword in sql_query.lower() for keyword in destructive_keywords)

def apply_penalties_for_overdue_books():
    if 'user_ID' in session:
        overdue_books = query_db(
            """
            SELECT idR, due_date
            FROM borrow
            WHERE return_date IS NULL AND due_date < ? 
            """, (current_date,)
        )

        penalties_date = (datetime.now() + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')

        for book in overdue_books:
            active_penalty = query_db(
                """
                SELECT idP 
                FROM penalties 
                WHERE status = 1 AND idR = ?
                """, (book[0],), one=True
            )

            if not active_penalty:
                execute_db(
                    """
                    INSERT INTO penalties (idR, end_time, status)
                    VALUES (?, ?, ?)
                    """, (book[0], penalties_date, 1)
                )

def check_penalties_end():
    if 'user_ID' in session:
        penalties = query_db(
            """
            SELECT idP
            FROM penalties
            WHERE end_time < ? AND status = ? 
            """, (current_date, 1, )
        )

        if penalties:
            for penalty in penalties:
                execute_db(
                    """
                    UPDATE penalties 
                    SET status = ?
                    WHERE idP = ?
                    """, (0, penalty[0])
                )

@app.route('/', methods=['POST', 'GET'])
def home():
    check_penalties_end()
    apply_penalties_for_overdue_books()
    if "user_ID" in session:
        if request.method == 'POST':
            search = request.form['search']
            book_info = query_db(
                """
                SELECT * FROM books WHERE title LIKE ? OR author LIKE ?
                """, ('%' + search + '%', '%' + search + '%')
            )

            if book_info:
                return render_template("book_search.html", book_info=book_info)
            else:
                flash("No books found matching your search criteria.", "error")
                return redirect(url_for('home'))

        top_borrowed = query_db(
            """
            SELECT idB, COUNT(*) AS borrow_count
            FROM borrow
            GROUP BY idB
            ORDER BY borrow_count DESC
            LIMIT 5;
            """
        )

        famous_books = [
            query_db("SELECT * FROM books WHERE idB = ?", (book[0],), one=True)
            for book in top_borrowed
        ]
        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("""
                SELECT idB
                FROM borrow
                WHERE idR = ?
                ORDER BY idBr DESC
                LIMIT ?
            """, (session['user_ID'],5))
            result = cur.fetchall()

            with open('tfidf_matrix.pkl', 'rb') as f:
                tfidf_matrix = pickle.load(f)

            cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
            ids = set()
            for book in result:
                book_index = books_df.index[books_df['idB'] == book].tolist()[0]
                similar_books = list(enumerate(cosine_sim[book_index]))
                similar_books = sorted(similar_books, key=lambda x: x[1], reverse=True)
                top_similar_books = similar_books[1:4]
                for _, score in top_similar_books:
                    if score > 0:
                        ids.add(books_df.iloc[_]['idB'])
            book_info_list = []
            for id in ids:
                cur.execute("SELECT * FROM books WHERE idB = ?", (str(id),))
                book_info = cur.fetchone()
                if book_info:
                    book_info_list.append(book_info)


        return render_template("main.html", logged_in=True, famous_books=famous_books,book_info_list = book_info_list )
    return render_template("main.html", logged_in=False)

@app.route('/login', methods=['POST', 'GET'])
def login():
    check_penalties_end()
    apply_penalties_for_overdue_books()
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = query_db("SELECT * FROM authentication WHERE email = ?", (email,), one=True)

        if user and bcrypt.checkpw(password.encode('utf-8'), user[7].encode('utf-8')):
            session['user_ID'] = user[0]
            session['user_name'] = user[2]
            return redirect(url_for('home'))
        else:
            msg = "Invalid email or password. Please try again."
            return render_template('login.html', msg=msg)

    return render_template('login.html')

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        fname = request.form['first_name']
        lname = request.form['last_name']
        profession = request.form['profession']
        address = request.form['address']
        email = request.form['email']
        password = request.form['password']
        cpassword = request.form['con-password']

        if password != cpassword:
            msg = "Error: Passwords do not match!"
            return render_template('register.html', msg=msg)

        existing_user = query_db("SELECT Email FROM Authentication WHERE Email = ?", (email,), one=True)

        if existing_user:
            msg = "Error: Email already exists. Please use a different email."
            return render_template('register.html', msg=msg)

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        execute_db(
            """
            INSERT INTO Authentication (Fname, Lname, Profession, Address, NbrOfBorrowedBooks, Email, Password) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fname, lname, profession, address, 0, email, hashed_password.decode('utf-8'))
        )

        msg = "Account created successfully!"
        return render_template('login.html', msg=msg)

    return render_template('register.html')

@app.route('/book', methods=['POST', 'GET'])
def book():
    check_penalties_end()
    apply_penalties_for_overdue_books()
    if "user_ID" in session:
        book_id = request.args.get('book_id', '')
        book = query_db("SELECT * FROM books WHERE idB = ?", (book_id,), one=True)

        if not book:
            flash("Book not found!", "error")
            return redirect(url_for("home"))

        if request.method == 'POST':
            penalty = query_db("SELECT * FROM penalties WHERE idR = ? AND status = ?", (session['user_ID'], 1), one=True)
            if penalty:
                flash("You have penalties and cannot borrow books!", "error")
                return redirect(url_for("book", book_id=book[0]))

            borrowed_books = query_db("SELECT NbrOfBorrowedBooks FROM authentication WHERE idR = ?", (session['user_ID'],), one=True)
            if borrowed_books and borrowed_books[0] >= 4:
                flash("You have reached the borrow limit of 4 books!", "error")
                return redirect(url_for("book", book_id=book[0]))

            already_borrowed = query_db(
                "SELECT * FROM borrow WHERE idR = ? AND idB = ? AND return_date IS NULL",
                (session['user_ID'], book[0]), one=True
            )
            if already_borrowed:
                flash("You have already borrowed this book!", "error")
                return redirect(url_for("book", book_id=book[0]))

            if book[4] <= 0:
                flash("No copies of this book are available!", "error")
                return redirect(url_for("book", book_id=book[0]))

            due_date = (datetime.now() + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            execute_db(
                """
                INSERT INTO borrow (idB, idR, borrow_date, due_date, return_date) 
                VALUES (?, ?, ?, ?, NULL)
                """, (book[0], session['user_ID'], current_date, due_date)
            )
            execute_db(
                """
                UPDATE authentication
                SET NbrOfBorrowedBooks = NbrOfBorrowedBooks + 1
                WHERE idR = ?;
                """, (session['user_ID'],)
            )
            execute_db(
                """
                UPDATE books
                SET Copy = Copy - 1
                WHERE idB = ?;
                """, (book[0],)
            )
            flash("Book borrowed successfully!", "success")
            return redirect(url_for("book", book_id=book[0]))

        return render_template('book.html', title=book[1], author=book[2], url=book[3], description=book[5], genre=book[6])
    return redirect(url_for('login'))

@app.route("/logout")
def logout():
    session.pop("user_ID", None)
    session.pop("admin_ID", None)
    session.clear()
    return redirect(url_for("home"))

@app.route("/profile")
def profile():
    if "user_ID" in session:
        result = query_db("SELECT * FROM Authentication WHERE idR = ?", (session['user_ID'],), one=True)
        borrowed_books = query_db(
            """
            SELECT books.*
            FROM borrow, books
            WHERE borrow.idR = ? AND borrow.idB = books.idB AND borrow.return_date IS NULL
            """, (session['user_ID'],)
        )
        penalty = query_db("SELECT end_time FROM penalties WHERE idR = ? AND status = ?", (session['user_ID'], 1), one=True)

        return render_template(
            'profile.html',
            result=result,
            borrowed_books=borrowed_books,
            penalty=penalty
        )
    return redirect(url_for('login'))

@app.route('/<int:book_id>')
def return_book(book_id):
    if 'user_ID' not in session:
        return redirect(url_for('login'))

    borrow_record = query_db(
        "SELECT idBr FROM borrow WHERE idR = ? AND idB = ? AND return_date IS NULL",
        (session['user_ID'], book_id), one=True
    )
    if not borrow_record:
        flash("Error: No active borrow record found for this book and user.", "error")
        return redirect(url_for('profile'))

    execute_db(
        """
        UPDATE borrow
        SET return_date = ?
        WHERE idBr = ?;
        """, (current_date, borrow_record[0])
    )
    execute_db(
        """
        UPDATE authentication
        SET NbrOfBorrowedBooks = NbrOfBorrowedBooks - 1
        WHERE idR = ?;
        """, (session['user_ID'],)
    )
    execute_db(
        """
        UPDATE books
        SET Copy = Copy + 1
        WHERE idB = ?;
        """, (book_id,)
    )
    return redirect(url_for('profile', _external=True))

@app.route('/admin', methods=['POST', 'GET'])
def admin():
    if "admin_ID" not in session:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            try:
                admin = query_db("SELECT * FROM admin WHERE email = ?", (email,), one=True)
                if admin and bcrypt.checkpw(password.encode('utf-8'), admin[2].encode('utf-8')):
                    session['admin_ID'] = admin[0]
                    return redirect(url_for('admin_panel'))
                else:
                    flash("Invalid email or password. Please try again.", "error")
            except Exception as e:
                flash(f"Error: {str(e)}", "error")
            return redirect(url_for("admin"))
        return render_template('admin.html')
    return redirect(url_for("admin_panel"))

@app.route("/admin_panel", methods=['POST', 'GET'])
def admin_panel():
    if "admin_ID" in session:
        if request.method == 'POST':
            reader_id = request.form.get('reader_id')
            book_id_ = request.form.get('id_book')
            book_title = request.form.get('book_title')
            book_author = request.form.get('book_author')
            book_url = request.form.get('book_url')
            book_copy = request.form.get('book_copy')
            book_description = request.form.get('book_description')
            book_category = request.form.get('book_category')
            p_reader_id = request.form.get('p_reader_id')
            end_date_penalty = request.form.get('end_date_penalty')
            penalty_id = request.form.get('id_penalty')
            id_copy = request.form.get('id_copy')
            num_copy = request.form.get('num_copy')
            sql_query = request.form.get('sql_query')

            if reader_id:
                user_s = query_db("SELECT * FROM authentication WHERE idR = ?", (reader_id,), one=True)
                if not user_s:
                    flash("Reader not found!", "error")
                else:
                    flash("Reader Found!", "success")
                    session.update({
                        'user_id': user_s[0],
                        'user_fname': user_s[1],
                        'user_lname': user_s[2],
                        'user_profession': user_s[3],
                        'user_nbb': user_s[5],
                        'user_email': user_s[6],
                        'user_address': user_s[4]
                    })
                return redirect(url_for('admin_panel'))

            if book_id_:
                execute_db("DELETE FROM books WHERE idB = ?", (book_id_,))
                flash("Book removed successfully", "success")
                return redirect(url_for('admin_panel'))

            if penalty_id:
                execute_db("DELETE FROM penalties WHERE idP = ?", (penalty_id,))
                flash("Penalty removed successfully", "success")
                return redirect(url_for('admin_panel'))

            if p_reader_id and end_date_penalty:
                execute_db(
                    """
                    INSERT INTO penalties (idR, end_time, status)
                    VALUES (?, ?, ?)
                    """, (p_reader_id, end_date_penalty, 1)
                )
                flash("Penalty added successfully", "success")
                return redirect(url_for('admin_panel'))

            if book_copy and book_url and book_author and book_title and book_description and book_category:
                execute_db(
                    """
                    INSERT INTO books (title, author, url, copy , description, categories)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (book_title, book_author, book_url, book_copy ,book_description, book_category)
                )
                conn = sqlite3.connect('database.db')
                query = """
                SELECT idB, title, description, author, categories
                FROM books
                """
                books_df = pd.read_sql(query, conn)

                books_df['combined_features'] = (
                        books_df['title'].fillna('') + ' ' +
                        books_df['description'].fillna('') + ' ' +
                        books_df['author'].fillna('') + ' ' +
                        books_df['categories'].fillna('')
                )
                vectorizer = TfidfVectorizer(stop_words='english')
                tfidf_matrix = vectorizer.fit_transform(books_df['combined_features'])
                with open('vectorizer.pkl', 'wb') as f:
                    pickle.dump(vectorizer, f)

                with open('tfidf_matrix.pkl', 'wb') as f:
                    pickle.dump(tfidf_matrix, f)
                flash("Book added successfully!", "success")
                return redirect(url_for('admin_panel'))

            if id_copy and num_copy:
                execute_db("UPDATE books SET copy = ? WHERE idB = ?", (num_copy, id_copy))
                flash("Copy added successfully", "success")
                return redirect(url_for('admin_panel'))

            if sql_query:
                if not is_valid_sql(sql_query):
                    flash("You can't drop or remove.", "error")
                else:
                    try:
                        results = query_db(sql_query)
                        if results:
                            session['results'] = results
                            flash("Query executed successfully.", "success")
                        else:
                            flash("Invalid Query!", "error")
                    except Exception as e:
                        flash(f"Error executing query: {str(e)}", "error")
                return redirect(url_for('admin_panel'))

        admin_user = query_db("SELECT * FROM admin WHERE id = ?", (session['admin_ID'],), one=True)
        return render_template('admin_panel.html', user=admin_user)
    return redirect(url_for("admin"))


if __name__ == '__main__':
    app.run( debug=True)