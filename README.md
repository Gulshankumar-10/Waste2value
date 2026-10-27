# Waste2Value — Working MVP

A responsive marketplace prototype for recovered materials. It includes an admin inventory workflow, buyer requests, SQLite storage, filtering and a stock update when a request is approved.

## Run locally
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Demo accounts
- Admin: `admin@waste2value.local` / `Admin@123`
- Buyer: `buyer@waste2value.local` / `Buyer@123`

The app creates the SQLite database and sample listings on first run. Sample rates, quantities and locations are illustrative only.

## Current working features
- Landing page and responsive design
- Search listings by title, description or location
- Filter by material and condition
- Admin can add listings
- Buyer can request a quantity and add a message
- Admin can approve/reject pending requests
- Approving a request deducts quantity from available inventory
- Buyer and admin dashboards; request history
- Server-side validation and password hashing

## Before a real public business launch
This is an MVP, not a security-audited production service. Before onboarding real users:
1. Set a strong random `SECRET_KEY` environment variable.
2. Remove demo credentials and seed data; implement secure account creation and password reset.
3. Add CSRF protection, rate limiting, email verification, audit logging and monitoring.
4. Use a production WSGI server, HTTPS and a persistent/managed database with backups. SQLite on ephemeral hosting may lose data after redeploy.
5. Add terms, privacy policy, verified listings, dispute/transport workflows and confirm applicable waste/e-waste rules.
6. Replace all sample inventory with verified material data. Do not present demo figures as actual impact.
7. Payments, shipping, municipal integrations and automatic physical sorting are not included.

## Stack
Python, Flask, SQLite (`sqlite3`), HTML, CSS, Jinja templates.
