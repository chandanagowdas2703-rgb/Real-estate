# HomeFinder - Real Estate Listing Platform

Flask + SQLite + Bootstrap 5 college project with three roles: Buyer/Renter, Seller/Agent, Admin.

## Folder structure
```
realestate/
├── app.py              # Flask app, database models, routes and demo-data seeder
├── requirements.txt
├── templates/          # Jinja2 pages (base.html, _card.html, index.html, ...)
└── static/
    ├── css/style.css
    ├── js/main.js
    ├── images/         # placeholder property images
    └── uploads/        # uploaded property photos (created automatically)
```

## Run locally
```bash
python -m venv venv
venv\Scripts\activate          # Windows      (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py seed             # optional: demo data
python app.py                  # open http://127.0.0.1:5000
```
The SQLite file `realestate.db` and the default amenities are created automatically on first start. Running
`python app.py seed` creates the demo accounts and ensures at least 20 approved listings for each property type
without deleting existing database records. The database file is stored in this project folder.
Bootstrap, icons and fonts load from a CDN, so you need an internet connection.
Property photos and illustrations are stored locally in `static/images`; the demo seeder assigns local photos to its sample listings.

## Demo accounts (after `python app.py seed`)
| Role   | Email               | Password  |
|--------|---------------------|-----------|
| Admin  | admin@example.com   | admin123  |
| Seller | seller@example.com  | seller123 |
| Buyer  | buyer@example.com   | buyer123  |

Admins cannot self-register; create more by editing a user's `role` in the database.

## How it works
- **Registration** creates buyer or seller accounts. Passwords are salted hashes (Werkzeug).
- **Seller** adds a listing -> status `pending` -> admin approves/rejects -> only `approved` listings are public.
  Editing a listing sends it back to `pending`. Sellers can only edit/delete their own listings (403 otherwise).
- **Buyer** can search/filter, favourite, and send inquiries (shown to the seller under *Inquiries*).
- **Admin** sees stats, approves/rejects/deletes listings, deletes users (and their data).
- **Security basics:** role checks on every protected route, CSRF token on every POST form, upload extension checks,
  16 MB request limit, safe `next` redirects. Change `SECRET_KEY` before deploying
  (`set SECRET_KEY=something-long-and-random`).

## Suggested optional improvements
1. **Google Maps:** add `latitude`/`longitude` columns, then replace the map placeholder in
   `property_detail.html` with the Maps JavaScript API (or an embedded iframe using the address).
2. **Pagination:** use `Property.query...paginate(page=page, per_page=9)` in `/properties` and render Bootstrap pagination.
3. **Recommendations:** on the detail page show approved listings with the same city and property type
   and a price within +/-25 percent.
4. **Seller extras:** choose the main image, drag-to-reorder photos, a "featured" flag, email notifications on new inquiries.
5. **Quality:** Flask-WTF forms, Flask-Migrate for schema changes, automated tests with pytest, image resizing with Pillow.

## Deployment (e.g. Render / PythonAnywhere)
1. Push the project to GitHub (the `.gitignore` is already set).
2. `pip install gunicorn` and add it to `requirements.txt`; start command: `gunicorn app:app`.
3. Set the `SECRET_KEY` environment variable.
4. Switch to PostgreSQL for production (change `SQLALCHEMY_DATABASE_URI`, add `psycopg2-binary`).
5. Uploaded images need persistent storage (a disk volume or cloud storage such as S3/Cloudinary);
   many free hosts wipe local files on restart.
