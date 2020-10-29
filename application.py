# export FLASK_APP=application.py
# export API_KEY=pk_7dbf239de0c34920905ac2112f81db74

import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Emptying database
    # db.execute("DELETE FROM stock")

    # Create an list (of dictionary)
    datas = []

    # Get stock
    stocks = db.execute("SELECT * FROM stock \
            WHERE user_id = :U_id ORDER BY symbol", \
            U_id = session['user_id'])

    # Get current user's remaining cash
    cash = db.execute("SELECT cash FROM users \
            WHERE id = :U_id", U_id = session['user_id'])
    cash = cash[0]['cash']

    # Make variable to store total price of all stock
    grandTotal = 0

    # Make a list of lookup's data
    for stock in stocks:

        # Store look up return values in a temp variable
        temp = lookup(stock['symbol'])

        # Count each stock value and add it to 'total'
        value = stock['share'] * temp['price']
        grandTotal += value

        # Append look up's return values in 'datas'
        datas.append({'name': temp['name'], 'price': usd(temp['price']), 'value': usd(value)})

    # Display data and stock value in index.html
    return render_template("index.html", data = datas, stock = stocks,\
                            cash = usd(cash), total = usd(grandTotal + cash), \
                            limit = len(stocks))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get symbol
        symbol = request.form.get("symbol").upper()

        # Ensure symbol was submitted
        if not symbol:
            return apology("must provide symbol")

        # Ensure symbol existance
        query = lookup(symbol)
        if query is None:
            return apology("symbol is invalid")

        # Get share
        shares = int(request.form.get("shares"))

        # Ensure share was submitted
        if not shares:
            return apology("must provide shares")

        # Ensure share is a positive integer
        if shares < 0:
            return apology("shares must be a positive integer")

        # PROCESS DATA
        rows = db.execute("Select cash FROM users WHERE id = :x", x = session['user_id'])
        cash = rows[0]['cash']
        cost = query['price'] * shares

        # If cash is enough to buy x amount of shares
        if cash >= cost:
            cash -= cost

            # Update history database
            db.execute("INSERT INTO history(symbol, change, price) \
                        VALUES(:sym, :ch, :pr)", sym = symbol, \
                        ch = shares ,pr = usd(query['price']))

            # Update user's cash
            db.execute("UPDATE users SET cash = :cash WHERE id = :x", \
                        cash = cash, x = session['user_id'])

            # See stock existancy in database
            stock = db.execute("SELECT * FROM stock WHERE user_id = :x AND symbol = :y", \
                                    x = session['user_id'], y = symbol)

            # Update user's stock
            if stock:
                tmp = stock[0]['share']
                db.execute("UPDATE stock SET share = :x WHERE user_id = :y AND symbol = :z", \
                            x = tmp + shares, y = session['user_id'], z = symbol)
            else:
                db.execute("INSERT INTO stock(symbol, share, user_id) VALUES(:sym, :shar, :Id)", \
                            sym = symbol, shar = shares, Id = session['user_id'])

            # Redirect user to homepage
            return redirect("/")

        # If cash isn't enough
        else:
            return apology("cash isn't enough")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Emptying history database
    # db.execute("DELETE FROM history")

    # Get history database
    data = db.execute("SELECT * FROM history")

    return render_template("history.html", history = data)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
@login_required
def quote():
    """Get stock quote."""

    # User reached route via post (as by submitting a form via POST)
    if request.method == "POST":

        # Get symbol
        symbol = request.form.get("symbol")

        # Search symbol in API
        query = lookup(symbol)

        # Redirect based on query
        if query is None:
            return apology("Invalid Symbol", 400)
        else:
            return render_template("quoted.html", name = query['name'], symbol = query['symbol'], price = usd(query['price']))

    # User reached route via get (as by clicking the link or register)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Emptying database
    # db.execute("DELETE FROM users")
    # db.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'users'")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get username and check database
        _username = request.form.get("username")
        query = db.execute("SELECT username FROM users WHERE username = :name", name=_username)

        # Ensure username was submitted
        if not _username or len(_username) == 1:
            return apology("username is unavailable", 403)

        # Ensure username haven't exist yet
        elif len(query) != 0:
            return apology("username already exist", 403)

        # Get password and verif-password
        password = request.form.get("password")
        verifPass = request.form.get("verifPass")

        # Ensure password was submitted
        if not password:
            return apology("must provide password", 403)

        # Ensure password was re-submitted
        elif not verifPass or password != verifPass:
            return apology("must provide the same password", 403)

        # Insert username and password hash into database
        db.execute("INSERT INTO users (username, hash) VALUES (:name, :Pass)",
                    name = _username, Pass = generate_password_hash(password))

        # Redirect user to home page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get symbol
        symbol = request.form.get("symbol")

        # Ensure symbol was submitted
        if not symbol:
            return apology("must provide symbol")

        # Get share
        shares = int(request.form.get("shares"))

        # Ensure share was submitted
        if not shares:
            return apology("must provide shares")

        # Ensure share is a positive integer
        if shares < 0:
            return apology("shares must be a positive integer")

        # Get current user's stock data
        datas = db.execute("SELECT * FROM users \
                            JOIN stock ON users.id = stock.user_id \
                            WHERE users.id = :U_id AND symbol = :sym", \
                            U_id = session['user_id'], sym = symbol)

        # Ensure the share is enough
        if shares <= datas[0]['share']:

            # Get name and price of the symbol
            query = lookup(symbol)

            # Update history database
            db.execute("INSERT INTO history(symbol, change, price) \
                        VALUES(:sym, :ch, :pr)", sym = symbol, \
                        ch = -shares ,pr = usd(query['price']))

            # Get current amount of cash
            cash = datas[0]['cash']

            # Get amount of money gained from sold share
            profit = query['price'] * shares

            # Get current amount of shares
            db_shares = datas[0]['share']

            # Add user's cash
            db.execute("UPDATE users SET cash = :total WHERE id = :U_id", \
                        total = cash + profit, U_id = session['user_id'])

            # Reduce user's stock share
            if shares == datas[0]['share']:
                db.execute("DELETE FROM stock WHERE user_id = :U_id AND symbol = :sym", \
                            U_id = session['user_id'], sym = symbol)
            else:
                db.execute("UPDATE stock SET share = :total \
                            WHERE user_id = :U_id AND symbol = :sym", \
                            total = db_shares - shares, U_id = session['user_id'], sym = symbol)

            # Redirect user to homepage
            return redirect("/")

        # If amount of share to be sold exced amount of owned share
        else:
            return apology("share exceed amount of owned share")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("Select symbol FROM stock WHERE user_id = :U_id \
                            ORDER BY symbol", U_id = session["user_id"])
        return render_template("sell.html", stocks = stocks)


@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    """ Change Password """

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get all rows
        C_pass = request.form.get("C_pass")
        N_pass = request.form.get("N_pass")
        V_pass = request.form.get("V_pass")

        # Ensure that all rows has input
        if not C_pass or not N_pass or not V_pass:
            return apology("Please input all rows in the form")

        # Ensure that N_pass is equal to V_pass
        if N_pass != V_pass:
            return apology("Insert the same password in the new password rows")

        # Get users password data in database
        data = db.execute("SELECT hash FROM users WHERE id = :U_id", U_id = session['user_id'])

        # Check whether C_pass is the same with the pass in the database
        if check_password_hash(data[0]['hash'], C_pass):

            # Ensure that N_pass is not equal to C_pass
            N_pass = generate_password_hash(N_pass)

            if check_password_hash(N_pass, C_pass):
                return apology("New password is the same as current password")

            # Updata hash in users database
            db.execute("UPDATE users SET hash = :n_hash WHERE id = :U_id", \
                        n_hash = N_pass, U_id = session['user_id'])

            return redirect("/")
        else:
            return apology("Wrong current password")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("cPass.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
