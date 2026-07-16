# Maison Vault — E-commerce Demo with Fraud Screening

A three-page store (item listing → cart → payment) with a Flask backend. Pressing
**Complete purchase** calls the backend `complete()` function, which internally calls
`fraud_check()`. Blocked attempts appear on the **Admin** page.

## Run it

```bash
pip install flask
python app.py
```

Then open http://127.0.0.1:5000

## Pages

| URL         | Page                                        |
|-------------|---------------------------------------------|
| `/`         | Item listing (add pieces to your cart)       |
| `/cart`     | View your cart (change quantities, totals)   |
| `/checkout` | Payment page (Complete purchase button)      |
| `/admin`    | Blocked transactions with fraud reasons      |

## Fraud rules (`fraud_check()` in app.py)

1. **Amount > $2,000** — order total exceeds the limit.
2. **Different country** — any item's seller country differs from the buyer's billing country.
3. **Too many transactions** — more than 20 purchase attempts in the last hour.
4. **Night-time purchase** — the purchase happens between 2:00 AM and 6:00 AM.

If any rule fires, `complete()` returns `{"status": "failure", "reasons": [...]}` to the
checkout page, the message is displayed in a red banner, and the transaction is logged
to the admin page. Otherwise it returns `{"status": "success"}` and the cart is emptied.

## How to test each rule

- **Amount**: add the Sapphire Tennis Bracelet ($2,350) and check out.
- **Country**: buy any piece that "Ships from" a country different from your selected billing country.
- **Velocity**: complete 21+ purchases within an hour (a loop with `curl` works well).
- **Night-time**: open "Demo controls" on the payment page and set the override hour to `3`.

## Notes

- Data is stored in memory (`TRANSACTION_LOG`, `BLOCKED_TRANSACTIONS`) and resets on
  restart — swap these for MySQL tables if you want persistence.
- The card fields are for show only; no payment data is processed or stored.
