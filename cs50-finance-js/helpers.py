import csv
import urllib.request

from flask import redirect, render_template, request, session, url_for
from functools import wraps


def apology(message, code=400):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code # the code parameter tells flask what status code of rendered page shall be


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login')) # redirect("/login") -> changed to url_for to keep dynamism
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol, name=None):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None
        
    if len(symbol) > 5:
        return None

    # reject symbol if it contains comma
    '''
    # check for special chars - could use isalpha, but tickers sometimes contain dot
    '''
    if any(i in '1234567890,~!@#$%^&()*+:"<>?_=/-\'; ' for i in symbol):
        return None
    else:

        # query Yahoo for quote -> does not work anymore
        # http://stackoverflow.com/a/21351911
        try:
    
            # GET CSV
            url = f"http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={symbol}"
            
            '''
            f-string, see https://docs.python.org/3/reference/lexical_analysis.html#f-strings
            '''
            webpage = urllib.request.urlopen(url)
    
            # read CSV
            datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
    
            # parse first row
            row = next(datareader)
    
            # ensure stock exists
            try:
                price = float(row[2])
            except:
                return None
    
            # return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
            return {
                "name": row[1],
                "price": price,
                "symbol": row[0].upper()
            }
    
        except:
            pass
    
        # query Alpha Vantage for quote instead
        # https://www.alphavantage.co/documentation/
        try:
    
            # GET CSV
            url = f"https://www.alphavantage.co/query?apikey=NAJXWIA8D6VN6A3K&datatype=csv&function=TIME_SERIES_INTRADAY&interval=1min&symbol={symbol}"
            webpage = urllib.request.urlopen(url)
    
            # parse CSV
            datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
    
            # ignore first row
            next(datareader)
    
            # parse second row
            row = next(datareader)
    
            # ensure stock exists
            try:
                price = float(row[4])
            except:
                return None
    
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
            
    
            # return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
            return {
                "name": company, # changed to support ticker convertor, orignal cs50 staff's design was: "name": symbol.upper(), # for backward compatibility with Yahoo
                "price": price,
                "symbol": symbol.upper()
            }
    
        except:
            return None


def usd(value):
    """Formats value as USD."""
    return f"$ {value:,.2f}"

        