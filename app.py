import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    stock = db.execute("SELECT symbol, SUM(amount), price FROM trans WHERE user_id = ? GROUP BY symbol HAVING SUM(amount) > 0", session["user_id"])
    cash = (db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]['cash'])
    stocks_total = db.execute("SELECT sum(amount*price) FROM trans WHERE user_id = ?", session["user_id"])[0]["sum(amount*price)"]
    if stocks_total == None:
        stocks_total = 0
    grand = cash + stocks_total
    return render_template("index.html", stock=stock, current=cash, grand=grand)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("must provide shares")

        if not request.form.get("symbol"):
            return apology("must provide symbol")
        elif not shares:
            return apology("must provide shares")
        elif shares < 1:
            return apology("must provide shares")
        elif symbol == None:
            return apology("Symbol doesn't exist")

        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        a = cash[0]['cash']-symbol['price']*int(shares)

        if a < 1:
            return apology("Not enough cash")

        db.execute("UPDATE users SET cash = ? WHERE id = ?", a, session["user_id"])
        db.execute(" INSERT INTO trans (user_id, symbol, amount, price, type) VALUES(?, ?, ?, ?, 'Bought')", session["user_id"], request.form.get("symbol").upper(), int(shares), symbol["price"])

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    stock = db.execute("SELECT * FROM trans WHERE user_id = ?", session["user_id"])
    return render_template("history.html", stock=stock)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if lookup(request.form.get("symbol")) == None:
            return apology("symbol doesn't exist")
        else:
            return render_template("quoted.html", stock=lookup(request.form.get("symbol")))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username")

        elif not request.form.get("password"):
            return apology("must provide password")

        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation")
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 0:
            return apology("This username already exists")

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))
        flash('You were successfully registred')
        return render_template("login.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = lookup(request.form.get("symbol"))
        shares = request.form.get("shares")

        if not shares:
            return apology("must provide shares")
        elif int(shares) > int(db.execute("SELECT SUM(amount) FROM trans WHERE user_id = ? AND symbol = ?", session["user_id"], request.form.get("symbol"))[0]["SUM(amount)"]):
            return apology("not enough shares")

        a = symbol["price"] * int(shares)
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", a, session["user_id"])
        db.execute("INSERT INTO trans (user_id, symbol, amount, price, type) VALUES(?, ?, ?, ?, 'Sold')", session["user_id"], request.form.get("symbol").upper(), -int(shares), symbol["price"])
        return redirect("/")
    else:
        return render_template("sell.html", stock=db.execute("SELECT symbol FROM trans WHERE user_id = ? GROUP BY symbol HAVING SUM(amount) > 0", session["user_id"]))

