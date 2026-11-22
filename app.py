from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import sqlite3
from pathlib import Path

app = Flask(__name__)
import os
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")
DB_PATH = Path(__file__).with_name("sas.db")

ROLES = ("customer", "sales_clerk", "vendor", "manager")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('customer','sales_clerk','vendor','manager'))
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            supplier TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            clerk_id INTEGER,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES users(id),
            FOREIGN KEY(clerk_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS stock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            vendor_id INTEGER,
            quantity INTEGER NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(vendor_id) REFERENCES users(id)
        );
        """)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            demo_users = [
                ("Demo Customer", "customer@sas.com", generate_password_hash("1234"), "customer"),
                ("Demo Clerk", "clerk@sas.com", generate_password_hash("1234"), "sales_clerk"),
                ("Demo Vendor", "vendor@sas.com", generate_password_hash("1234"), "vendor"),
                ("Demo Manager", "manager@sas.com", generate_password_hash("1234"), "manager"),
            ]
            db.executemany("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", demo_users)
        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            products = [
                ("G001", "Rice 1 kg", "Grocery", 65, 50, "ABC Suppliers"),
                ("G002", "Sugar 1 kg", "Grocery", 48, 40, "ABC Suppliers"),
                ("D001", "Milk 1 litre", "Dairy", 30, 35, "Fresh Dairy"),
                ("B001", "Bread", "Bakery", 40, 25, "Daily Bakers"),
                ("H001", "Bath Soap", "Household", 35, 60, "Care Distributors"),
                ("S001", "Shampoo", "Personal Care", 120, 20, "Care Distributors"),
            ]
            db.executemany("INSERT INTO products(code,name,category,price,stock,supplier) VALUES(?,?,?,?,?,?)", products)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def cart_items(db):
    cart = session.get("cart", {})
    items, total = [], 0
    for product_id, quantity in cart.items():
        product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if product:
            subtotal = product["price"] * int(quantity)
            items.append({"product": product, "quantity": int(quantity), "subtotal": subtotal})
            total += subtotal
    return items, total

@app.context_processor
def inject_globals():
    return {"current_user": session.get("name"), "current_role": session.get("role")}

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 4:
            flash("Enter your name, a valid email and a password of at least 4 characters.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                               (name, email, generate_password_hash(password), "customer"))
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"], cart={})
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as db:
        product_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        low_stock = db.execute("SELECT COUNT(*) FROM products WHERE stock < 10").fetchone()[0]
        sales_total = db.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0]
        recent_sales = db.execute("""SELECT s.*, u.name customer_name FROM sales s
            LEFT JOIN users u ON s.customer_id=u.id ORDER BY s.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", product_count=product_count, low_stock=low_stock,
                           sales_total=sales_total, recent_sales=recent_sales)

@app.route("/products")
@login_required
def products():
    search = request.args.get("q", "").strip()
    with get_db() as db:
        rows = db.execute("""SELECT * FROM products WHERE name LIKE ? OR code LIKE ? OR category LIKE ?
                             ORDER BY name""", (f"%{search}%",)*3).fetchall()
    return render_template("products.html", products=rows, search=search)

@app.route("/cart/add/<int:product_id>", methods=["POST"])
@roles_required("customer")
def add_to_cart(product_id):
    with get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product or product["stock"] < 1:
        flash("This product is unavailable.", "danger")
    else:
        cart = session.get("cart", {})
        key = str(product_id)
        new_qty = int(cart.get(key, 0)) + 1
        if new_qty > product["stock"]:
            flash("Requested quantity is greater than available stock.", "warning")
        else:
            cart[key] = new_qty
            session["cart"] = cart
            flash("Item added to cart.", "success")
    return redirect(url_for("products"))

@app.route("/cart")
@roles_required("customer")
def cart():
    with get_db() as db:
        items, total = cart_items(db)
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/update", methods=["POST"])
@roles_required("customer")
def update_cart():
    cart = session.get("cart", {})
    with get_db() as db:
        for product_id in list(cart.keys()):
            try:
                quantity = int(request.form.get(f"qty_{product_id}", 0))
            except ValueError:
                quantity = 0
            product = db.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()
            if quantity <= 0:
                cart.pop(product_id, None)
            elif product and quantity <= product["stock"]:
                cart[product_id] = quantity
            else:
                flash("A quantity exceeded available stock and was not updated.", "warning")
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
@roles_required("customer", "sales_clerk")
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("products"))
    payment = request.form.get("payment_method", "Cash")
    if payment not in ("Cash", "UPI (demo)", "Card (demo)"):
        payment = "Cash"
    customer_id = session["user_id"] if session["role"] == "customer" else None
    try:
        with get_db() as db:
            items, total = cart_items(db)
            if not items:
                flash("No valid items in cart.", "danger")
                return redirect(url_for("cart"))
            for item in items:
                current = db.execute("SELECT stock FROM products WHERE id=?", (item["product"]["id"],)).fetchone()
                if not current or current["stock"] < item["quantity"]:
                    raise ValueError("Insufficient stock for " + item["product"]["name"])
            cur = db.execute("""INSERT INTO sales(customer_id,clerk_id,total,payment_method,created_at)
                VALUES(?,?,?,?,?)""", (customer_id, session["user_id"] if session["role"] == "sales_clerk" else None,
                                       total, payment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            sale_id = cur.lastrowid
            for item in items:
                p = item["product"]
                db.execute("INSERT INTO sale_items(sale_id,product_id,quantity,unit_price) VALUES(?,?,?,?)",
                           (sale_id, p["id"], item["quantity"], p["price"]))
                db.execute("UPDATE products SET stock=stock-? WHERE id=?", (item["quantity"], p["id"]))
            db.commit()
        session["cart"] = {}
        return redirect(url_for("bill", sale_id=sale_id))
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("cart"))

@app.route("/bill/<int:sale_id>")
@login_required
def bill(sale_id):
    with get_db() as db:
        sale = db.execute("""SELECT s.*, u.name customer_name FROM sales s LEFT JOIN users u
                             ON s.customer_id=u.id WHERE s.id=?""", (sale_id,)).fetchone()
        if not sale:
            flash("Bill not found.", "danger")
            return redirect(url_for("dashboard"))
        lines = db.execute("""SELECT p.code,p.name,si.quantity,si.unit_price,
                              si.quantity*si.unit_price subtotal FROM sale_items si
                              JOIN products p ON p.id=si.product_id WHERE si.sale_id=?""", (sale_id,)).fetchall()
    return render_template("bill.html", sale=sale, lines=lines)

@app.route("/inventory")
@roles_required("manager", "vendor", "sales_clerk")
def inventory():
    with get_db() as db:
        rows = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("inventory.html", products=rows)

@app.route("/products/add", methods=["POST"])
@roles_required("manager")
def add_product():
    code, name = request.form.get("code","").strip(), request.form.get("name","").strip()
    category = request.form.get("category","General").strip()
    supplier = request.form.get("supplier","").strip()
    try:
        price, stock = float(request.form.get("price", 0)), int(request.form.get("stock", 0))
        if not code or not name or price < 0 or stock < 0:
            raise ValueError()
        with get_db() as db:
            db.execute("INSERT INTO products(code,name,category,price,stock,supplier) VALUES(?,?,?,?,?,?)",
                       (code,name,category,price,stock,supplier))
        flash("Product added.", "success")
    except (ValueError, sqlite3.IntegrityError):
        flash("Could not add product. Check the values and make sure the item code is unique.", "danger")
    return redirect(url_for("inventory"))

@app.route("/products/<int:product_id>/edit", methods=["POST"])
@roles_required("manager")
def edit_product(product_id):
    try:
        price = float(request.form.get("price", 0))
        stock = int(request.form.get("stock", 0))
        if price < 0 or stock < 0:
            raise ValueError()
        with get_db() as db:
            db.execute("UPDATE products SET price=?,stock=? WHERE id=?", (price,stock,product_id))
        flash("Product updated.", "success")
    except ValueError:
        flash("Enter a valid non-negative price and stock quantity.", "danger")
    return redirect(url_for("inventory"))

@app.route("/supply", methods=["GET", "POST"])
@roles_required("vendor", "manager")
def supply():
    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            note = request.form.get("note","").strip()
            if quantity <= 0:
                raise ValueError()
            with get_db() as db:
                product = db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
                if not product:
                    raise ValueError()
                db.execute("UPDATE products SET stock=stock+? WHERE id=?", (quantity,product_id))
                db.execute("""INSERT INTO stock_history(product_id,vendor_id,quantity,note,created_at)
                    VALUES(?,?,?,?,?)""", (product_id,session["user_id"],quantity,note,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            flash("Stock received and inventory updated.", "success")
        except (ValueError, KeyError):
            flash("Please select a product and enter a positive quantity.", "danger")
        return redirect(url_for("supply"))
    with get_db() as db:
        products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
        history = db.execute("""SELECT h.*,p.name product_name,u.name vendor_name FROM stock_history h
            JOIN products p ON p.id=h.product_id LEFT JOIN users u ON u.id=h.vendor_id
            ORDER BY h.id DESC LIMIT 30""").fetchall()
    return render_template("supply.html", products=products, history=history)


@app.route("/pos", methods=["GET", "POST"])
@roles_required("sales_clerk")
def pos():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        try:
            quantity = int(request.form.get("quantity", 0))
        except ValueError:
            quantity = 0
        with get_db() as db:
            product = db.execute("SELECT * FROM products WHERE code=?", (code,)).fetchone()
        if not product or quantity <= 0:
            flash("Enter a valid item code and positive quantity.", "danger")
        else:
            cart_data = session.get("cart", {})
            key = str(product["id"])
            new_quantity = int(cart_data.get(key, 0)) + quantity
            if new_quantity > product["stock"]:
                flash("Requested quantity is greater than available stock.", "warning")
            else:
                cart_data[key] = new_quantity
                session["cart"] = cart_data
                flash("Item added to checkout.", "success")
        return redirect(url_for("pos"))
    with get_db() as db:
        items, total = cart_items(db)
        all_products = db.execute("SELECT code,name,stock FROM products ORDER BY name").fetchall()
    return render_template("pos.html", items=items, total=total, products=all_products)

@app.route("/sales")
@roles_required("manager", "sales_clerk")
def sales():
    with get_db() as db:
        rows = db.execute("""SELECT s.*,u.name customer_name FROM sales s LEFT JOIN users u
            ON u.id=s.customer_id ORDER BY s.id DESC LIMIT 100""").fetchall()
    return render_template("sales.html", sales=rows)

@app.route("/reports")
@roles_required("manager")
def reports():
    with get_db() as db:
        total_sales = db.execute("SELECT COALESCE(SUM(total),0) FROM sales").fetchone()[0]
        count_sales = db.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        best = db.execute("""SELECT p.name,SUM(si.quantity) sold FROM sale_items si
            JOIN products p ON p.id=si.product_id GROUP BY p.id ORDER BY sold DESC LIMIT 5""").fetchall()
        low = db.execute("SELECT * FROM products WHERE stock < 10 ORDER BY stock").fetchall()
    return render_template("reports.html", total_sales=total_sales, count_sales=count_sales,
                           best=best, low=low)

@app.route("/users")
@roles_required("manager")
def users():
    with get_db() as db:
        rows = db.execute("SELECT id,name,email,role FROM users ORDER BY id").fetchall()
    return render_template("users.html", users=rows)

@app.route("/users/<int:user_id>/role", methods=["POST"])
@roles_required("manager")
def change_role(user_id):
    role = request.form.get("role")
    if role not in ROLES:
        flash("Invalid role.", "danger")
    elif user_id == session["user_id"]:
        flash("You cannot change your own role while logged in.", "warning")
    else:
        with get_db() as db:
            db.execute("UPDATE users SET role=? WHERE id=?", (role,user_id))
        flash("User role updated.", "success")
    return redirect(url_for("users"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)