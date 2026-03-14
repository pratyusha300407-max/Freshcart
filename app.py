from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask import send_from_directory
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT,
        approved INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER,
        name TEXT,
        price INTEGER,
        quantity INTEGER,
        image TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        status TEXT
    )
    """)

    # Create admin automatically
    cur.execute("SELECT * FROM users WHERE role='admin'")
    admin = cur.fetchone()

    if not admin:
        cur.execute("""
        INSERT INTO users(name,email,password,role,approved)
        VALUES(?,?,?,?,?)
        """, ("Admin","admin@gmail.com","admin123","admin",1))

    conn.commit()
    conn.close()
init_db()

# -------------------- HOME ---------------------

@app.route("/")
def index():
    return render_template("index.html")


# -------------------- AUTH ---------------------

@app.route("/auth", methods=["GET","POST"])
def auth():
    if request.method == "POST":

        action = request.form["action"]

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        if action == "register":

            name = request.form["name"]
            role = request.form["role"]

            approved = 0 if role=="farmer" else 1

            cur.execute("INSERT INTO users(name,email,password,role,approved) VALUES(?,?,?,?,?)",
                        (name,email,password,role,approved))
            conn.commit()

            return "Registered Successfully! Wait for admin approval."

        if action == "login":

            cur.execute("SELECT * FROM users WHERE email=? AND password=?",
                        (email,password))
            user = cur.fetchone()

            if user:

                if user[4]=="farmer" and user[5]==0:
                    return "Waiting for admin approval"

                session["user_id"]=user[0]
                session["role"]=user[4]

                if user[4]=="farmer":
                    return redirect("/farmer_dashboard")

                if user[4]=="customer":
                    return redirect("/products")

            return "Invalid Login"

    return render_template("auth.html")


# -------------------- FARMER DASHBOARD ---------------------

@app.route("/farmer_dashboard")
def farmer_dashboard():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products WHERE farmer_id=?",
                (session["user_id"],))

    products = cur.fetchall()
    cur.execute("""
    SELECT orders.id,products.name,orders.quantity
    FROM orders
    JOIN products ON orders.product_id=products.id
    WHERE products.farmer_id=? AND orders.status='ordered'
    """,(session["user_id"],))

    orders = cur.fetchall()

    return render_template("farmer_dashboard.html",products=products, orders=orders)


# -------------------- ADD PRODUCT ---------------------

@app.route("/add_product", methods=["GET","POST"])
def add_product():

    if request.method=="POST":

        name = request.form["name"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        image = request.files["image"]
        filename = secure_filename(image.filename)

        image.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""INSERT INTO products
        (farmer_id,name,price,quantity,image)
        VALUES(?,?,?,?,?)""",
        (session["user_id"],name,price,quantity,filename))

        conn.commit()

        return redirect("/farmer_dashboard")

    return render_template("add_product.html")


# -------------------- DELETE PRODUCT ---------------------

@app.route("/delete/<id>")
def delete_product(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM products WHERE id=?",(id,))
    conn.commit()

    return redirect("/farmer_dashboard")

@app.route("/edit_product/<int:id>", methods=["GET","POST"])

def edit_product(id):

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        cur.execute("""
        UPDATE products
        SET name=?, price=?, quantity=?
        WHERE id=?
        """,(name,price,quantity,id))

        conn.commit()

        return redirect("/farmer_dashboard")

    cur.execute("SELECT * FROM products WHERE id=?", (id,))
    product = cur.fetchone()

    return render_template("edit_product.html",product=product)
# -------------------- PRODUCTS ---------------------

@app.route("/products")
def products():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    return render_template("products.html",products=products)


# -------------------- ADD TO CART ---------------------
@app.route("/add_to_cart/<int:id>", methods=["POST"])
def add_to_cart(id):

    qty = request.form["quantity"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO orders(user_id,product_id,quantity,status)
    VALUES(?,?,?,?)
    """,(session["user_id"],id,qty,"cart"))

    conn.commit()

    return redirect("/cart")

@app.route("/order_now/<int:id>", methods=["POST"])
def order_now(id):

    qty = request.form["quantity"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO orders(user_id,product_id,quantity,status)
    VALUES(?,?,?,?)
    """,(session["user_id"],id,qty,"ordered"))

    conn.commit()

    return redirect("/cart")
# -------------------- CART ---------------------

@app.route("/cart")
def cart():

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    SELECT orders.id,products.name,products.price,orders.quantity
    FROM orders
    JOIN products ON orders.product_id=products.id
    WHERE orders.user_id=? AND orders.status='cart'
    """,(session["user_id"],))
    
    items = cur.fetchall()

    return render_template("cart.html",items=items)


# -------------------- ADMIN ---------------------

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db()
    cur = conn.cursor()

    # farmers count
    cur.execute("SELECT COUNT(*) FROM users WHERE role='farmer'")
    farmers = cur.fetchone()[0]

    # customers count
    cur.execute("SELECT COUNT(*) FROM users WHERE role='customer'")
    customers = cur.fetchone()[0]

    # items sold
    cur.execute("SELECT SUM(quantity) FROM orders WHERE status='delivered'")
    sold = cur.fetchone()[0]

    # pending farmers
    cur.execute("SELECT * FROM users WHERE role='farmer' AND approved=0")
    pending = cur.fetchall()

    # farmer details
    cur.execute("SELECT * FROM users WHERE role='farmer'")
    farmer_details = cur.fetchall()

    # customer details
    cur.execute("SELECT * FROM users WHERE role='customer'")
    customer_details = cur.fetchall()

    return render_template(
        "admin_dashboard.html",
        farmers=farmers,
        customers=customers,
        sold=sold,
        pending=pending,
        farmer_details=farmer_details,
        customer_details=customer_details
    )

@app.route("/approve/<id>")
def approve(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("UPDATE users SET approved=1 WHERE id=?",(id,))
    conn.commit()

    return redirect("/admin_dashboard")


@app.route("/reject/<id>")
def reject(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id=?",(id,))
    conn.commit()

    return redirect("/admin_dashboard")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/place_order/<int:id>", methods=["POST"])
def place_order(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    UPDATE orders
    SET status='ordered'
    WHERE id=?
    """,(id,))

    conn.commit()

    return redirect("/cart")
@app.route("/deliver/<int:id>")
def deliver(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    UPDATE orders
    SET status='delivered'
    WHERE id=?
    """,(id,))

    conn.commit()

    return redirect("/farmer_dashboard")


@app.route("/admin_login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM users
        WHERE email=? AND password=? AND role='admin'
        """,(email,password))

        admin = cur.fetchone()

        if admin:
            session["admin"] = admin[0]
            return redirect("/admin_dashboard")

        else:
            return "Invalid Admin Login"

    return render_template("admin_login.html")
# --------------------

if __name__ == "__main__":
    app.run(debug=True)