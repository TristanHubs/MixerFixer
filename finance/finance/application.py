import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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

    # alle eigendommen van current user
    alle_eigendommen = db.execute("SELECT * FROM eigendommen WHERE user_id = :id", id=session["user_id"])

    # waarde totaal aandelen van current user
    aandelen_geld = 0
    for i in alle_eigendommen:
        aandelen_geld += i['total']

    # selecteer cash van current user
    row = db.execute('SELECT cash FROM users WHERE id = :id', id=session["user_id"])
    cash = float(row[0]["cash"])

    # cash optellen bij totale waarde van aandelen van current user
    total = cash + aandelen_geld

    # als er geen eigendommen zijn, apology
    if len(alle_eigendommen) < 1:
       # return apology("There are no shares in your posession.")
       return render_template("index.html", cash=usd(10000), total=usd(10000))

    return render_template("index.html", aandelen=alle_eigendommen, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # kijken of shares numeriek is
        if shares.isdigit() == False:
            return apology("Shares must be numeric.")

        shares = int(shares)

        # check of symbol bestaat
        if lookup(symbol) == None:
            return apology("Symbol does not exists.")

        # invalid shares
        if shares < 1:
            return apology("Shares cannot be negative.")

        # selecteer cash van current user
        row = db.execute('SELECT cash FROM users WHERE id = :id', id=session["user_id"])
        cash = float(row[0]["cash"])

        # geeft de 'stock quote', bijvoorbeeld: {"name":"Netflix, Inc.", "price":318.83, "symbol":"NFLX"}
        stock_quote = lookup(symbol)

        # reken uit wat de prijs is van de shares user wil kopen
        current_price = stock_quote["price"] * shares

        cash_after_purchase = cash - current_price

        # wanneer bedrag groter is dan geld wat user heeft, apology
        if cash_after_purchase < 0:
            return apology("not enough money")

        elif cash_after_purchase > 0:
            # cash updaten
            update_cash = db.execute("UPDATE users SET cash = :cash_after_purchase WHERE id = :id", cash_after_purchase=cash_after_purchase, id=session["user_id"])

            # checken of dit symbool al in de 'portfolio' zit
            symbol_check = db.execute("SELECT symbol FROM eigendommen WHERE symbol = ? AND user_id = ?", stock_quote["symbol"], session["user_id"])

            if not symbol_check:
                print('if')
                # de aandelen van deze transactie toevoegen aan de portfolio
                toevoegen_eigendommen = db.execute("INSERT INTO eigendommen (symbol, name, shares, price, total, user_id) VALUES (:symbol, :name, :shares, :price, :total, :user_id)", symbol=stock_quote["symbol"], name=stock_quote["name"], shares=shares, price=stock_quote["price"], total=(stock_quote["price"]*shares), user_id=session["user_id"])

            # als er nog geen aankopen zijn van een symbool
            else:
                print('else')
                # de aandelen in de portfolio aanpassen aan deze transactie, nieuwe aandelen optellen bij huidige aandelen
                updaten_eigendommen1 = db.execute("UPDATE eigendommen SET shares = shares + :shares, total = total + :total WHERE symbol = :symbol", shares=shares, total=(stock_quote["price"]*shares), symbol=stock_quote["symbol"])

            return redirect("/")

    else:
        return render_template("buy.html")


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
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # symbool opvragen
        symbol = request.form.get("symbol")
        info = lookup(symbol)

        # als er geen symbool wordt ingetypt
        if not symbol:
            return apology("Must provide a symbol.")

        # als het symbool niet bestaat
        if lookup(symbol) == None:
            return apology("Symbol doesn't exist.")

        return render_template("quoted.html", symbol=info["symbol"], name=info["name"], price=usd(info["price"]))

    else:
        return render_template("quote.html")


# lijst met gebruikersnamen
usernames = []

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":

        # gebruikersnaam opvragen
        username = request.form.get("username")

        # voor als de gebruikersnaam mist
        if not username:
            return apology("Missing username")

        # voor als de gebruikersnaam al bestaat
        if username in usernames:
            return apology("Username already exists")

        # gebruikersnaam toevoegen aan de lijst
        usernames.append(username)

        # wachtwoord en confirmatie opvragen
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # voor als het wachtwoord of de confirmatie mist
        if not password:
            return apology("Missing password")
        if not confirmation:
            return apology("Missing password confirmation")

        # het wachtwoord en de confirmatie moeten hetzelfde zijn
        if password != confirmation:
            return apology("Password doesn't match password confirmation")

        # gegevens toevoegen aan de database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))

        return redirect("/")

    else:
        return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # symbol & shares opvragen
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # checken of er wel een symbool geselecteerd is
        if not symbol:
            return apology("Must select a symbol.")

        # alle eigendommen van current user
        alle_eigendommen = db.execute("SELECT * FROM eigendommen WHERE user_id = :id", id=session["user_id"])

        # alle bedrijven waar de current user aandelen van heeft (in symbolen)
        symbol_eigendommen = db.execute("SELECT symbol FROM eigendommen WHERE user_id = :id", id=session["user_id"])
        # [{'symbol': 'NFLX'}, {'symbol': 'CMD'}, {'symbol': 'MSD'}]

        # lijst aanmaken met symbolen waarvan current user eigenaar is
        symbol_lijst = []
        for i in symbol_eigendommen:
            symbol_lijst.append(i["symbol"])

        # checken of het geselecteerde symbool onder de eigendommen valt van de current user
        if symbol not in symbol_lijst:
            return apology("No shares of this stock.")

        # invalid shares
        if shares < 1:
            return apology("Shares cannot be negative.")

        # aantal shares van de current user van ingevulde stock
        row = db.execute("SELECT shares FROM eigendommen WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=symbol)
        shares_user = int(row[0]["shares"])

        if shares_user < shares:
            return apology("Not enough shares owned of stock.")

        # geeft de 'stock quote', bijvoorbeeld: {"name":"Netflix, Inc.", "price":318.83, "symbol":"NFLX"}
        stock_quote = lookup(symbol)

        # selecteer cash van current user
        row = db.execute('SELECT cash FROM users WHERE id = :id', id=session["user_id"])
        cash = float(row[0]["cash"])

        # reken uit wat de prijs is van de shares die de user wil verkopen
        current_price = stock_quote["price"] * shares
        cash_after_sale = cash + current_price

        # bijwerken cash
        update_cash = db.execute("UPDATE users SET cash = :cash_after_sale WHERE id = :id", cash_after_sale=cash_after_sale, id=session["user_id"])

        # verkopen van shares
        verkoop = db.execute("UPDATE eigendommen SET shares = shares - :shares, total = total - :total WHERE symbol = :symbol", shares=shares, total=(stock_quote["price"]*shares), symbol=stock_quote["symbol"])

        return redirect("/")

    else:
        # alle eigendommen van current user
        alle_eigendommen = db.execute("SELECT * FROM eigendommen WHERE user_id = :id", id=session["user_id"])

        return render_template("sell.html", aandelen=alle_eigendommen)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
