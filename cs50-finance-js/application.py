from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")



# ==================== QUOTE - AJAX ====================

@app.route("/quoteajax")
def quoteajax():
    symbol = request.args.get("symbol")
    name = request.args.get("name")
    url = f"https://www.alphavantage.co/query?apikey=NAJXWIA8D6VN6A3K&datatype=csv&function=TIME_SERIES_INTRADAY&interval=1min&symbol={symbol}"
    webpage = urllib.request.urlopen(url)
    datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
    next(datareader)
    row = next(datareader)
    
    # ensure stock exists
    try:
        price = float(row[4])
    except:
        return jsonify({
            "name": 0,
            "price": 0,
            "symbol": 0
        })

     # load also company name if called from /quote view
    if name:
        
        ''' ticker to company name convetor - beginning
        http://docs.python-guide.org/en/latest/scenarios/scrape/
        ''' 
        
        try:
            from lxml import html
            import requests
            
            page = requests.get(f"https://www.marketwatch.com/investing/stock/{symbol}")
            tree = html.fromstring(page.content)
            company = tree.xpath('//h1[@class="company__name"]/text()')[0] # looks up <h1 class="company__name">{symbol}</h1> at 'page'
        except:
            company = symbol.upper() # if error, proceed as initially designed by cs50 staff
            
        ''' end ticker convertor '''
    else: # company name stored in DB, no need to load again
        company = symbol.upper()
    
    
    
    
    return jsonify({
        "name": company,
        "price": float(row[4]),
        "symbol": symbol.upper()
    })

# ==================== REGISTER ====================

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # show reg form
    if request.method == "GET":
        return render_template("register.html")
    
    # evaluate reg form
    elif request.method =="POST":
        
        # store form data for repeated usage
        username = request.form.get("username")
        password = request.form.get("password")
        
        # check inputs
        if not username:
            return apology("no username provided")
            
        elif not password:
            return apology("no password provided")
            
        elif password != request.form.get("passwordAgain"):
            return apology("passwords don't match")
            
        else:
            # lookup if username already exists
            rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
            
            if len(rows) != 0:
                return apology("username already taken")
            
            else:
                # clear session
                session.clear()
                
                # insert user into DB
                newuser = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=username, hash=pwd_context.hash(password))

                # log newly registered user in
                session["user_id"] = newuser
                
                # redirect to dashboard
                flash("Registered!")
                return redirect(url_for("index"))


# ==================== LOGIN ====================

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))  # do not use .format method to prevent SQL inject

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


# ==================== DASHBOARD ====================

@app.route("/")
@login_required
def index():
    
    # retrieve user cash
    rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    userCash = rows[0]["cash"]
    
    # retrieve unique symbols owned
    rows2 = db.execute("SELECT SUM(shares) as sharesOwned, symbol, name FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING sharesOwned <> 0", 
    user_id=session["user_id"])
    
    # append actual share price & calculate value of owned shares
    
    ownedStockValue = 0
    
    for row in rows2:
        # get quote
        quote = lookup(row["symbol"])
        
        if not quote:
            return apology("cant quote one of the symbols")
        else:
            # append up to date price information
            row["price"] = quote["price"]
            row["sum"] = row["price"] * row["sharesOwned"]
            ownedStockValue += row["sum"]

    return render_template("index.html", userCash=userCash, rows2=rows2, ownedStockValue=ownedStockValue)


# ==================== BUY ====================

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    if request.method == "GET":
        
        return render_template("buy.html")
    
    elif request.method == "POST":
        
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        
        # check if mandatory form data provided
        if not symbol:
            return apology("no symbol provided")
            
        elif not shares:
            return apology("no shares provided")
        
        # check if shares are a digit, also handles exclusion of float
        elif not shares.isdigit():
            return apology("shares can only be digit")
  
        # elif float(shares):
           # return apology("can buy only whole shares")
        
        # cant buy zero shares
        elif int(shares) == 0:
            return apology(f"cant buy {shares} shares")
            
        else:
            # lookup stock price, second argument tells the lookup function to also convert symbol to company name

            quote = lookup(symbol, symbol)
            
            if not quote:
                return apology("invalid symbol")

            # get user balance
            rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            balance = rows[0]["cash"]
            
            # check for sufficient funds
            totalCost = int(shares) * float(quote["price"])
            
            if totalCost > balance:
                return apology("insufficient funds")
                
            else:
                # insert info stocks table
                newTransaction = db.execute("INSERT INTO transactions (user_id, shares, symbol, price, date, name) VALUES(:user_id, :shares, :symbol, :price, :date, :name)", 
                user_id=session["user_id"], shares=shares, symbol=quote["symbol"], price=quote["price"], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                name=quote["name"])
                
                # update funds
                updateFunds = db.execute("UPDATE users SET cash = :cash WHERE id = :id", id=session["user_id"], cash=(balance-totalCost))
                
                flash("Bought!")
                return redirect(url_for("index"))

# ==================== BUY_MULTIPLE ====================

@app.route("/buy_multiple", methods=["GET", "POST"])
@login_required
def buy_multiple():
    
    if request.method == "POST":
        
        ''' get form data. Could get also quotes & names lists directly from form via hidden field to avoid quote check, but since stock trading
        is time-sensitive, i decided to quote for up to date price each time '''
        
        symbols = request.form.getlist("symbol")
        shares = request.form.getlist("shares")

        # check if mandatory form data provided & correct
        if not symbols:
            return apology("no symbols")
        
        if not shares:
            return apology("no shares")

        quotes = []
        names = []
        sharesToBuy = 0
        sharesValueToBuy = 0

        for i in range(len(symbols)):
            if not shares[i].isdigit():
                return apology("shares can only be digits")
            
            if shares[i] == "" or shares[i] == "0":
                quotes.append(0)
                names.append("blank")
                sharesToBuy += 0
            else:
                quote = lookup(symbols[i], symbols[i])
                if not quote:
                    return apology("invalid symbol")
                    
                else:
                    quotes.append(float(quote["price"]))
                    names.append(quote["name"])
                    sharesValueToBuy += int(shares[i]) * quotes[i]
                    sharesToBuy += int(shares[i])
        
        if sharesToBuy == 0:
            return apology(f"cant buy zero shares")
        
        else:
            # compare with user balance
            rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            balance = rows[0]["cash"]
            
            if sharesValueToBuy > balance:
                return apology("insufficient funds")
            else:
                # record transaction one by one
                for i in range(len(symbols)):
                    if shares[i] == "" or shares[i] == "0":
                        pass
                    else:
                        transaction = db.execute("INSERT INTO transactions (user_id, shares, symbol, price, date, name) VALUES(:user_id, :shares, :symbol, :price, :date, :name)", 
                        user_id=session["user_id"], shares=shares[i], symbol=symbols[i], price=quotes[i], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name=names[i])
                
                # update funds
                updateFunds = db.execute("UPDATE users SET cash = :cash WHERE id = :id", id=session["user_id"], cash=(balance-sharesValueToBuy))
                
                flash("Bought!")
                return redirect(url_for("index"))
                # return render_template("test2.html", symbols=symbols, shares=shares, quotes=quotes, sharesToBuy=sharesToBuy, balance=balance)
            
    elif request.method == "GET":
        return redirect(url_for("index"))

# ==================== QUOTE ====================

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    
    if request.method == "GET":
        return render_template("quote.html", rm=request.method)
    
    elif request.method == "POST":
        
        symbol = request.form.get("symbol")
        
        if not symbol:
            return apology("no symbol provided")
        
        else:
            """Get stock quote."""
            quote = lookup(symbol, symbol)
            
            if not quote:
                return apology("invalid symbol")
                
            flash("Quote obtained")
            return render_template("quote.html", rm=request.method, quote=quote)


# ==================== SELL ====================

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    
    if request.method == "GET":
        
        # find out symbol of stock owned by user
        rows = db.execute("SELECT SUM(shares) as sharesOwned, symbol FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING sharesOwned <> 0", 
        user_id=session["user_id"])
        
        return render_template("sell.html", rows=rows)
        
    elif request.method =="POST":
        
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        
        # check that inputs are correct
        if not symbol:
            return apology("no symbol provided")
        
        elif not shares:
            return apology("no shares")
        
        elif not shares.isdigit():
            return apology("shares can only be digit")

        # elif float(shares):
            # return apology("can sell only whole shares")
            
        elif int(shares) == 0:
            return apology(f"cant sell {shares} shares")

        else:

            # lookup stock price
            quote = lookup(symbol, name)
            
            if not quote:
                return apology("invalid symbol")
            
            # get amount of owned shares
            
            rows = db.execute("SELECT SUM(shares) AS sharesOwned FROM transactions WHERE user_id = :user_id AND symbol = :symbol GROUP BY symbol", user_id=session["user_id"], symbol=symbol)
            
            # check if user has sufficient shares to sell
            
            if int(shares) > rows[0]["sharesOwned"]:
                return apology("too many shares to sell")
                
            else:
                # get user balance
                rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
                balance = rows[0]["cash"]

                # insert info stocks table
                newTransaction = db.execute("INSERT INTO transactions (user_id, shares, symbol, price, date, name) VALUES(:user_id, :shares, :symbol, :price, :date, :name)", 
                user_id=session["user_id"], shares=(-int(shares)), symbol=quote["symbol"], price=quote["price"], date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name=quote["name"])
                
                soldSharesValue = int(shares) * float(quote["price"])
                
                # update funds
                updateFunds = db.execute("UPDATE users SET cash = :cash WHERE id = :id", id=session["user_id"], cash=(balance+soldSharesValue))
    
                flash("Sold!")
                return redirect(url_for("index"))
        

# --------------------------------- transaction history view ---------------------------------

@app.route("/history")
@login_required
def history():
    
    # get history of transactions
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
    
    return render_template("history.html", rows=rows)
    
# --------------------------------- logout function ---------------------------------

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))