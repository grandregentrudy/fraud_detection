"""
Maison Vault — demo jewellery store with server-side fraud screening.

Flow:
  Checkout page -> POST /api/complete-purchase -> complete() -> fraud_check()
  fraud_check() evaluates four rules and returns (passed, reasons).
  Failures are stored in BLOCKED_TRANSACTIONS and shown on /admin.

Run:
  pip install flask
  python app.py
  open http://127.0.0.1:5000
"""

from datetime import datetime, timedelta
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = "demo-secret-change-me"

SELLER_COUNTRY_DEFAULT = "IN"

# ----------------------------------------------------------------------------
# Catalogue (each item carries its seller's country for the fraud check)
# ----------------------------------------------------------------------------
PRODUCTS = [
    {"id": 1, "name": "Solitaire Diamond Ring",   "price": 1450.00, "seller_country": "IN", "meta": "18k white gold · 0.9 ct", "image":"solitairediamondring.jpg"},
    {"id": 2, "name": "Emerald Drop Earrings",    "price": 780.00,  "seller_country": "IN", "meta": "Zambian emerald · pavé halo", "image":"emeralddropearrings.jpg"},
    {"id": 3, "name": "Sapphire Tennis Bracelet", "price": 2350.00, "seller_country": "CH", "meta": "Ceylon sapphire · 7 in", "image":"sapphiretennisbracelet.jpg"},
    {"id": 4, "name": "Baroque Pearl Strand",     "price": 540.00,  "seller_country": "JP", "meta": "Akoya pearls · 45 cm", "image":"baroquepearlstrand.jpg"},
    {"id": 5, "name": "Ruby Signet Ring",         "price": 990.00,  "seller_country": "IN", "meta": "Burmese ruby · 14k gold", "image":"rubysignetring.jpg"},
    {"id": 6, "name": "Gold Curb Chain",          "price": 1120.00, "seller_country": "AE", "meta": "22k yellow gold · 55 g", "image":"goldcurbchain.jpg"},
]

COUNTRIES = ["IN", "US", "GB", "CH", "JP", "AE", "AU", "SG"]

# ----------------------------------------------------------------------------
# In-memory stores (swap for MySQL in production)
# ----------------------------------------------------------------------------
TRANSACTION_LOG = []        # timestamps of every purchase attempt (for rule 3)
BLOCKED_TRANSACTIONS = []   # dicts describing blocked purchases (for /admin)
COMPLETED_ORDERS = []


def _get_cart():
    return session.setdefault("cart", {})  # {product_id(str): qty}


def _cart_details():
    cart = _get_cart()
    items, total = [], 0.0
    for pid, qty in cart.items():
        product = next((p for p in PRODUCTS if p["id"] == int(pid)), None)
        if not product:
            continue
        line = product["price"] * qty
        total += line
        items.append({**product, "qty": qty, "line_total": round(line, 2)})
    return items, round(total, 2)


# ----------------------------------------------------------------------------
# Fraud engine
# ----------------------------------------------------------------------------
FRAUD_AMOUNT_LIMIT = 2000.00
FRAUD_TX_PER_HOUR_LIMIT = 20
NIGHT_START_HOUR = 2   # inclusive
NIGHT_END_HOUR = 6     # exclusive


def fraud_check(amount, buyer_country, seller_countries, purchase_time):
    """Evaluate the four fraud rules. Returns (passed: bool, reasons: list[str])."""
    reasons = []

    # Rule 1 — high value: amount greater than $2000
    if amount > FRAUD_AMOUNT_LIMIT:
        reasons.append(
            f"High-value order: ${amount:,.2f} exceeds the ${FRAUD_AMOUNT_LIMIT:,.0f} limit."
        )

    # Rule 2 — cross-border: any seller country differs from the buyer country
    mismatched = sorted({c for c in seller_countries if c != buyer_country})
    if mismatched:
        reasons.append(
            f"Cross-border purchase: buyer in {buyer_country}, seller(s) in {', '.join(mismatched)}."
        )

    # Rule 3 — velocity: more than 20 transactions in the last hour
    one_hour_ago = purchase_time - timedelta(hours=1)
    recent = [t for t in TRANSACTION_LOG if t >= one_hour_ago]
    if len(recent) > FRAUD_TX_PER_HOUR_LIMIT:
        reasons.append(
            f"Velocity limit: {len(recent)} transactions in the last hour "
            f"(limit {FRAUD_TX_PER_HOUR_LIMIT})."
        )

    # Rule 4 — night-time purchase between 2 AM and 6 AM
    if NIGHT_START_HOUR <= purchase_time.hour < NIGHT_END_HOUR:
        reasons.append(
            f"Night-time purchase at {purchase_time.strftime('%I:%M %p')} "
            f"(flagged window 2:00 AM – 6:00 AM)."
        )

    return (len(reasons) == 0), reasons


def complete(buyer_name, buyer_country, items, total, override_hour=None):
    """Called when the Complete Purchase button is pressed.
    Internally calls fraud_check() and returns a result dict."""
    now = datetime.now()
    if override_hour is not None:  # demo control for testing the night rule
        now = now.replace(hour=override_hour)

    TRANSACTION_LOG.append(now)

    seller_countries = [i["seller_country"] for i in items]
    passed, reasons = fraud_check(total, buyer_country, seller_countries, now)

    record = {
        "id": uuid4().hex[:8].upper(),
        "buyer": buyer_name or "Guest",
        "buyer_country": buyer_country,
        "seller_countries": sorted(set(seller_countries)),
        "amount": total,
        "items": [{"name": i["name"], "qty": i["qty"]} for i in items],
        "time": now.strftime("%Y-%m-%d %I:%M %p"),
    }

    if not passed:
        record["reasons"] = reasons
        BLOCKED_TRANSACTIONS.append(record)
        return {"status": "failure", "order_id": record["id"], "reasons": reasons}

    COMPLETED_ORDERS.append(record)
    return {"status": "success", "order_id": record["id"]}


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------
@app.route("/")
def listing():
    return render_template("index.html", products=PRODUCTS, cart_count=sum(_get_cart().values()))


@app.route("/cart")
def cart_page():
    items, total = _cart_details()
    return render_template("cart.html", items=items, total=total, cart_count=sum(_get_cart().values()))


@app.route("/checkout")
def checkout_page():
    items, total = _cart_details()
    return render_template("checkout.html", items=items, total=total,
                           countries=COUNTRIES, cart_count=sum(_get_cart().values()))


@app.route("/admin")
def admin_page():
    return render_template("admin.html", blocked=list(reversed(BLOCKED_TRANSACTIONS)),
                           completed_count=len(COMPLETED_ORDERS))


# ----------------------------------------------------------------------------
# APIs
# ----------------------------------------------------------------------------
@app.post("/api/cart/add")
def api_cart_add():
    pid = str(request.json.get("product_id"))
    cart = _get_cart()
    cart[pid] = cart.get(pid, 0) + 1
    session.modified = True
    return jsonify({"cart_count": sum(cart.values())})


@app.post("/api/cart/update")
def api_cart_update():
    pid = str(request.json.get("product_id"))
    qty = max(0, int(request.json.get("qty", 0)))
    cart = _get_cart()
    if qty == 0:
        cart.pop(pid, None)
    else:
        cart[pid] = qty
    session.modified = True
    items, total = _cart_details()
    return jsonify({"items": items, "total": total, "cart_count": sum(cart.values())})


@app.post("/api/complete-purchase")
def api_complete_purchase():
    data = request.json or {}
    items, total = _cart_details()
    if not items:
        return jsonify({"status": "failure", "reasons": ["Your cart is empty."]}), 400

    override_hour = data.get("override_hour")
    override_hour = int(override_hour) if override_hour not in (None, "") else None

    result = complete(
        buyer_name=data.get("name", "").strip(),
        buyer_country=data.get("country", SELLER_COUNTRY_DEFAULT),
        items=items,
        total=total,
        override_hour=override_hour,
    )

    if result["status"] == "success":
        session["cart"] = {}  # empty the cart on success
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
