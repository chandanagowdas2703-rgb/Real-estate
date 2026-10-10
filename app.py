"""
HomeFinder - Real Estate Listing Platform (Flask).
Run:  python app.py seed   (optional sample data)
      python app.py
"""
import os
import re
import sys
import uuid
import secrets
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, session)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user, UserMixin)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------- database models
db = SQLAlchemy()

property_amenities = db.Table(
    "property_amenities",
    db.Column("property_id", db.Integer, db.ForeignKey("properties.id"), primary_key=True),
    db.Column("amenity_id", db.Integer, db.ForeignKey("amenities.id"), primary_key=True),
)

favorites = db.Table(
    "favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("property_id", db.Integer, db.ForeignKey("properties.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(10), nullable=False, default="buyer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    favorites = db.relationship("Property", secondary=favorites, backref="favorited_by")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Property(db.Model):
    __tablename__ = "properties"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    property_type = db.Column(db.String(30), nullable=False)
    listing_type = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending")
    price = db.Column(db.Float, nullable=False)
    bedrooms = db.Column(db.Integer, default=0)
    bathrooms = db.Column(db.Integer, default=0)
    area = db.Column(db.Float, default=0)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    pincode = db.Column(db.String(10))
    is_furnished = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User", backref="listings")
    images = db.relationship("PropertyImage", backref="property",
                             cascade="all, delete-orphan", order_by="PropertyImage.id")
    amenities = db.relationship("Amenity", secondary=property_amenities, backref="properties")
    inquiries = db.relationship("Inquiry", backref="property", cascade="all, delete-orphan")

    @property
    def main_image_url(self):
        for image in self.images:
            if image.is_main:
                return image.image_url
        if self.images:
            return self.images[0].image_url
        return "images/placeholder1.svg"


class PropertyImage(db.Model):
    __tablename__ = "property_images"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    is_main = db.Column(db.Boolean, default=False)


class Amenity(db.Model):
    __tablename__ = "amenities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)


class Inquiry(db.Model):
    __tablename__ = "inquiries"
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    contact_phone = db.Column(db.String(20))
    status = db.Column(db.String(10), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])

# ---------------------------------------------------------------- setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(BASE_DIR, "realestate.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=os.path.join(BASE_DIR, "static", "uploads"),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,   # reject requests bigger than 16 MB
)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"

PROPERTY_TYPES = ["Apartment", "House", "Villa", "Studio", "Plot", "Commercial"]
PROPERTY_IMAGE_FILES = {
    "Apartment": ["images/apartment.jpg", "images/studio.jpg", "images/house.jpg"],
    "House": ["images/house.jpg", "images/villa.jpg", "images/apartment.jpg"],
    "Villa": ["images/villa.jpg", "images/house.jpg", "images/apartment.jpg"],
    "Studio": ["images/studio.jpg", "images/apartment.jpg", "images/house.jpg"],
    "Plot": ["images/plot.jpg", "images/house.jpg", "images/villa.jpg"],
    "Commercial": ["images/commercial.jpg", "images/apartment.jpg", "images/house.jpg"],
}
LISTING_TYPES = ["sale", "rent"]
DEFAULT_AMENITIES = ["Parking", "Swimming Pool", "Gym", "Lift", "Garden", "24x7 Security",
                     "Power Backup", "Balcony", "Air Conditioning", "Clubhouse"]
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMAGES = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d[\d\s-]{6,14}$")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------- helpers
def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def to_number(value, cast=float):
    """Convert text to a number; return None when empty or invalid."""
    try:
        return cast(str(value).strip())
    except (TypeError, ValueError):
        return None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def validate_images(files):
    """Return (valid_files, errors). Empty file inputs are ignored."""
    files = [f for f in files if f and f.filename]
    errors = []
    if len(files) > MAX_IMAGES:
        errors.append(f"You can upload at most {MAX_IMAGES} images at a time.")
    for f in files:
        if not allowed_file(f.filename):
            errors.append(f"'{f.filename}' is not an allowed image type (png, jpg, jpeg, gif, webp).")
    return files, errors


def save_images(files, prop):
    """Save uploaded files to static/uploads and create PropertyImage rows."""
    has_main = any(i.is_main for i in prop.images)
    for f in files:
        name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], name))
        db.session.add(PropertyImage(property_id=prop.id, image_url=f"uploads/{name}",
                                     is_main=not has_main))
        has_main = True   # only the very first image becomes the main one


def remove_image_file(image):
    """Delete the file from disk (placeholders in static/images are never touched)."""
    if image.image_url.startswith("uploads/"):
        path = os.path.join(app.static_folder, image.image_url)
        if os.path.exists(path):
            os.remove(path)


def delete_property(prop):
    for img in prop.images:
        remove_image_file(img)
    db.session.delete(prop)   # images, inquiries and favourite links go with it


def parse_property_form(form):
    """Validate the add/edit form. Returns (clean_data, errors)."""
    errors = []
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "property_type": form.get("property_type", ""),
        "listing_type": form.get("listing_type", ""),
        "address": form.get("address", "").strip(),
        "city": form.get("city", "").strip(),
        "state": form.get("state", "").strip(),
        "pincode": form.get("pincode", "").strip(),
        "is_furnished": form.get("is_furnished") == "on",
    }
    for field, label in [("title", "Title"), ("description", "Description"),
                         ("address", "Address"), ("city", "City"), ("state", "State")]:
        if not data[field]:
            errors.append(f"{label} is required.")
    if data["property_type"] not in PROPERTY_TYPES:
        errors.append("Please choose a valid property type.")
    if data["listing_type"] not in LISTING_TYPES:
        errors.append("Please choose Sale or Rent.")
    if data["pincode"] and not re.fullmatch(r"\d{6}", data["pincode"]):
        errors.append("Pincode must be 6 digits.")

    price = to_number(form.get("price"))
    if price is None or price <= 0:
        errors.append("Price must be a number greater than 0.")
    data["price"] = price

    bedrooms = to_number(form.get("bedrooms") or 0, int)
    bathrooms = to_number(form.get("bathrooms") or 0, int)
    area = to_number(form.get("area") or 0)
    if bedrooms is None or bedrooms < 0:
        errors.append("Bedrooms must be 0 or more.")
    if bathrooms is None or bathrooms < 0:
        errors.append("Bathrooms must be 0 or more.")
    if area is None or area < 0:
        errors.append("Area must be 0 or more.")
    data.update(bedrooms=bedrooms, bathrooms=bathrooms, area=area)
    return data, errors


def selected_amenities(form):
    ids = [int(x) for x in form.getlist("amenities") if x.isdigit()]
    return Amenity.query.filter(Amenity.id.in_(ids)).all() if ids else []


def safe_next(target):
    """Only allow redirects to paths inside this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ---------------------------------------------------------------- template helpers
@app.before_request
def csrf_protect():
    """Very small CSRF check: every POST form must carry the session token."""
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or token != request.form.get("csrf_token"):
            abort(400)


@app.context_processor
def inject_globals():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    fav_ids = set()
    if current_user.is_authenticated and current_user.role == "buyer":
        fav_ids = {p.id for p in current_user.favorites}
    return dict(csrf_token=lambda: session["_csrf"], fav_ids=fav_ids,
                PROPERTY_TYPES=PROPERTY_TYPES,
                PROPERTY_IMAGE_FILES=PROPERTY_IMAGE_FILES,
                current_year=datetime.now().year)


@app.template_filter("money")
def money(value):
    """Format a price the Indian way: Rs 45.00 Lakh / Rs 1.20 Cr."""
    value = value or 0
    if value >= 1e7:
        return f"₹{value / 1e7:.2f} Cr"
    if value >= 1e5:
        return f"₹{value / 1e5:.2f} Lakh"
    return f"₹{value:,.0f}"


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400,
                           message="Your session expired or the form was invalid. Go back and try again."), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You do not have permission to do that."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="We could not find that page."), 404


@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", code=413, message="Upload too large (max 16 MB in total)."), 413


# ---------------------------------------------------------------- public pages
@app.route("/")
def index():
    featured = (Property.query.filter_by(status="approved")
                .order_by(Property.created_at.desc()).limit(6).all())
    rows = (db.session.query(Property.property_type, func.count(Property.id))
            .filter_by(status="approved").group_by(Property.property_type).all())
    counts = dict(rows)
    return render_template("index.html", featured=featured, counts=counts)


@app.route("/properties")
def properties():
    """Listing page + search/filter page in one (filters come from the query string)."""
    a = request.args
    q = Property.query.filter_by(status="approved")

    loc = a.get("q", "").strip()
    if loc:
        like = f"%{loc}%"
        q = q.filter(or_(Property.city.ilike(like), Property.state.ilike(like),
                         Property.address.ilike(like), Property.pincode.ilike(like),
                         Property.title.ilike(like)))
    if a.get("property_type") in PROPERTY_TYPES:
        q = q.filter(Property.property_type == a["property_type"])
    if a.get("listing_type") in LISTING_TYPES:
        q = q.filter(Property.listing_type == a["listing_type"])

    min_price, max_price = to_number(a.get("min_price")), to_number(a.get("max_price"))
    min_area, max_area = to_number(a.get("min_area")), to_number(a.get("max_area"))
    beds, baths = to_number(a.get("bedrooms"), int), to_number(a.get("bathrooms"), int)
    if min_price is not None:
        q = q.filter(Property.price >= min_price)
    if max_price is not None:
        q = q.filter(Property.price <= max_price)
    if min_area is not None:
        q = q.filter(Property.area >= min_area)
    if max_area is not None:
        q = q.filter(Property.area <= max_area)
    if beds:
        q = q.filter(Property.bedrooms >= beds)      # "2+" style filter
    if baths:
        q = q.filter(Property.bathrooms >= baths)

    sort = a.get("sort", "newest")
    order = {"price_asc": Property.price.asc(), "price_desc": Property.price.desc()}.get(
        sort, Property.created_at.desc())
    items = q.order_by(order).all()
    return render_template("properties.html", properties=items)


@app.route("/property/<int:property_id>")
def property_detail(property_id):
    prop = db.get_or_404(Property, property_id)
    is_staff = current_user.is_authenticated and (
        current_user.role == "admin" or prop.owner_id == current_user.id)
    if prop.status != "approved" and not is_staff:
        abort(404)   # hide unapproved listings from the public
    return render_template("property_detail.html", prop=prop)


# ---------------------------------------------------------------- auth
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        f = request.form
        name, email = f.get("full_name", "").strip(), f.get("email", "").strip().lower()
        phone, role = f.get("phone", "").strip(), f.get("role", "buyer")
        password, confirm = f.get("password", ""), f.get("confirm", "")
        errors = []
        if not name:
            errors.append("Full name is required.")
        if not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        elif User.query.filter(func.lower(User.email) == email).first():
            errors.append("An account with this email already exists.")
        if phone and not PHONE_RE.match(phone):
            errors.append("Phone number looks invalid.")
        if role not in ("buyer", "seller"):      # nobody can self-register as admin
            errors.append("Please choose a valid account type.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", form=f)
        user = User(full_name=name, email=email, phone=phone, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter(func.lower(User.email) == email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            flash(f"Welcome back, {user.full_name}!", "success")
            nxt = safe_next(request.args.get("next"))
            if nxt:
                return redirect(nxt)
            return redirect(url_for({"admin": "admin_dashboard",
                                     "seller": "seller_dashboard"}.get(user.role, "index")))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- buyer: favourites & inquiries
@app.route("/favorites")
@role_required("buyer")
def favorites_page():
    items = [p for p in current_user.favorites if p.status == "approved"]
    return render_template("favorites.html", properties=items)


@app.route("/favorite/<int:property_id>", methods=["POST"])
@role_required("buyer")
def toggle_favorite(property_id):
    prop = db.get_or_404(Property, property_id)
    if prop in current_user.favorites:
        current_user.favorites.remove(prop)
        flash("Removed from favorites.", "info")
    else:
        current_user.favorites.append(prop)
        flash("Saved to favorites.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("favorites_page"))


@app.route("/property/<int:property_id>/inquire", methods=["POST"])
@role_required("buyer")
def send_inquiry(property_id):
    prop = db.get_or_404(Property, property_id)
    if prop.status != "approved":
        abort(404)
    message = request.form.get("message", "").strip()
    phone = request.form.get("contact_phone", "").strip()
    if len(message) < 10:
        flash("Please write a message of at least 10 characters.", "danger")
    elif phone and not PHONE_RE.match(phone):
        flash("Contact phone looks invalid.", "danger")
    else:
        db.session.add(Inquiry(property_id=prop.id, buyer_id=current_user.id,
                               seller_id=prop.owner_id, message=message, contact_phone=phone))
        db.session.commit()
        flash("Your inquiry was sent to the seller.", "success")
    return redirect(url_for("property_detail", property_id=prop.id))


@app.route("/inquiries")
@role_required("buyer", "seller")
def inquiries():
    """Sellers see inquiries they received; buyers see the ones they sent."""
    column = Inquiry.seller_id if current_user.role == "seller" else Inquiry.buyer_id
    items = Inquiry.query.filter(column == current_user.id).order_by(Inquiry.created_at.desc()).all()
    return render_template("inquiries.html", inquiries=items)


@app.route("/inquiries/<int:inquiry_id>/read", methods=["POST"])
@role_required("seller")
def mark_inquiry_read(inquiry_id):
    inq = db.get_or_404(Inquiry, inquiry_id)
    if inq.seller_id != current_user.id:
        abort(403)
    inq.status = "read"
    db.session.commit()
    return redirect(url_for("inquiries"))


# ---------------------------------------------------------------- seller: manage listings
def form_values(prop):
    keys = ["title", "description", "property_type", "listing_type", "price", "bedrooms",
            "bathrooms", "area", "address", "city", "state", "pincode"]
    values = {k: getattr(prop, k) for k in keys}
    values["is_furnished"] = "on" if prop.is_furnished else ""
    return values


@app.route("/seller/dashboard")
@role_required("seller")
def seller_dashboard():
    items = (Property.query.filter_by(owner_id=current_user.id)
             .order_by(Property.created_at.desc()).all())
    stats = {s: sum(1 for p in items if p.status == s) for s in ("approved", "pending", "rejected")}
    new_inq = Inquiry.query.filter_by(seller_id=current_user.id, status="new").count()
    return render_template("seller_dashboard.html", properties=items, stats=stats, new_inq=new_inq)


@app.route("/seller/property/new", methods=["GET", "POST"])
@role_required("seller")
def add_property():
    if request.method == "POST":
        data, errors = parse_property_form(request.form)
        files, image_errors = validate_images(request.files.getlist("images"))
        errors += image_errors
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("property_form.html", prop=None, v=request.form,
                                   chosen=[int(x) for x in request.form.getlist("amenities") if x.isdigit()],
                                   amenities=Amenity.query.order_by(Amenity.name).all())
        prop = Property(owner_id=current_user.id, status="pending", **data)
        prop.amenities = selected_amenities(request.form)
        db.session.add(prop)
        db.session.flush()           # gives prop an id so images can reference it
        save_images(files, prop)
        db.session.commit()
        flash("Listing submitted. It will appear once an admin approves it.", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("property_form.html", prop=None, v={}, chosen=[],
                           amenities=Amenity.query.order_by(Amenity.name).all())


@app.route("/seller/property/<int:property_id>/edit", methods=["GET", "POST"])
@role_required("seller")
def edit_property(property_id):
    prop = db.get_or_404(Property, property_id)
    if prop.owner_id != current_user.id:     # sellers can only touch their own listings
        abort(403)
    if request.method == "POST":
        data, errors = parse_property_form(request.form)
        files, image_errors = validate_images(request.files.getlist("images"))
        errors += image_errors
        if len(prop.images) + len(files) > 20:
            errors.append("A listing can have at most 20 images.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("property_form.html", prop=prop, v=request.form,
                                   chosen=[int(x) for x in request.form.getlist("amenities") if x.isdigit()],
                                   amenities=Amenity.query.order_by(Amenity.name).all())
        for key, value in data.items():
            setattr(prop, key, value)
        prop.amenities = selected_amenities(request.form)
        prop.status = "pending"              # edited listings go back for admin review
        save_images(files, prop)
        db.session.commit()
        flash("Listing updated and sent for re-approval.", "success")
        return redirect(url_for("seller_dashboard"))
    return render_template("property_form.html", prop=prop, v=form_values(prop),
                           chosen=[a.id for a in prop.amenities],
                           amenities=Amenity.query.order_by(Amenity.name).all())


@app.route("/seller/image/<int:image_id>/delete", methods=["POST"])
@role_required("seller")
def delete_image(image_id):
    image = db.get_or_404(PropertyImage, image_id)
    prop = image.property
    if prop.owner_id != current_user.id:
        abort(403)
    was_main = image.is_main
    remove_image_file(image)
    db.session.delete(image)
    db.session.flush()
    remaining = PropertyImage.query.filter_by(property_id=prop.id).first()
    if was_main and remaining:
        remaining.is_main = True
    db.session.commit()
    flash("Image removed.", "info")
    return redirect(url_for("edit_property", property_id=prop.id))


@app.route("/seller/property/<int:property_id>/delete", methods=["POST"])
@role_required("seller")
def delete_own_property(property_id):
    prop = db.get_or_404(Property, property_id)
    if prop.owner_id != current_user.id:
        abort(403)
    delete_property(prop)
    db.session.commit()
    flash("Listing deleted.", "info")
    return redirect(url_for("seller_dashboard"))


# ---------------------------------------------------------------- admin
@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    stats = {
        "users": User.query.count(),
        "buyers": User.query.filter_by(role="buyer").count(),
        "sellers": User.query.filter_by(role="seller").count(),
        "listings": Property.query.count(),
        "approved": Property.query.filter_by(status="approved").count(),
        "pending": Property.query.filter_by(status="pending").count(),
        "rejected": Property.query.filter_by(status="rejected").count(),
        "inquiries": Inquiry.query.count(),
    }
    pending = Property.query.filter_by(status="pending").order_by(Property.created_at).all()
    return render_template("admin_dashboard.html", stats=stats, pending=pending)


@app.route("/admin/listings")
@role_required("admin")
def admin_listings():
    status = request.args.get("status", "")
    q = Property.query
    if status in ("pending", "approved", "rejected"):
        q = q.filter_by(status=status)
    return render_template("admin_listings.html", properties=q.order_by(Property.created_at.desc()).all(),
                           status=status)


@app.route("/admin/listings/<int:property_id>/<action>", methods=["POST"])
@role_required("admin")
def admin_listing_action(property_id, action):
    prop = db.get_or_404(Property, property_id)
    if action == "approve":
        prop.status = "approved"
        flash(f"'{prop.title}' approved.", "success")
    elif action == "reject":
        prop.status = "rejected"
        flash(f"'{prop.title}' rejected.", "warning")
    elif action == "delete":
        delete_property(prop)
        flash("Listing deleted.", "info")
    else:
        abort(404)
    db.session.commit()
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    return render_template("admin_users.html", users=User.query.order_by(User.created_at.desc()).all())


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def admin_delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.role == "admin":
        flash("Admin accounts cannot be deleted here.", "danger")
        return redirect(url_for("admin_users"))
    for prop in list(user.listings):
        delete_property(prop)                        # also removes inquiries on those listings
    Inquiry.query.filter_by(buyer_id=user.id).delete()
    user.favorites = []
    db.session.delete(user)
    db.session.commit()
    flash("User and their data deleted.", "info")
    return redirect(url_for("admin_users"))


# ---------------------------------------------------------------- start-up
def init_db():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    with app.app_context():
        db.create_all()
        if Amenity.query.count() == 0:
            db.session.add_all([Amenity(name=n) for n in DEFAULT_AMENITIES])
            db.session.commit()


init_db()


def seed_database():
    """Create demo accounts and ensure 20 approved listings per property type."""
    users_data = [
        ("Admin User", "admin@example.com", "admin123", "admin", "9000000001"),
        ("Asha Agent", "seller@example.com", "seller123", "seller", "9000000002"),
        ("Ben Buyer", "buyer@example.com", "buyer123", "buyer", "9000000003"),
    ]
    samples = [
        ("Sunny 3BHK near Indiranagar Metro", "Apartment", "sale", 12500000, 3, 3, 1650, "12 100 Feet Road", "Bengaluru", "560038", True, "approved"),
        ("Cozy Studio in Koramangala", "Studio", "rent", 24000, 1, 1, 450, "5th Block", "Bengaluru", "560095", True, "approved"),
        ("Spacious Villa with Garden", "Villa", "sale", 38500000, 4, 5, 3200, "Whitefield Main Road", "Bengaluru", "560066", False, "approved"),
        ("2BHK Family Flat", "Apartment", "rent", 32000, 2, 2, 1100, "HSR Layout Sector 2", "Bengaluru", "560102", False, "approved"),
        ("Independent House with Terrace", "House", "sale", 21000000, 3, 3, 2200, "Jayanagar 4th Block", "Bengaluru", "560011", False, "approved"),
        ("Corner Plot, Ready to Build", "Plot", "sale", 9500000, 0, 0, 2400, "Sarjapur Road", "Bengaluru", "560035", False, "approved"),
        ("Commercial Space on MG Road", "Commercial", "rent", 150000, 0, 2, 1800, "MG Road", "Bengaluru", "560001", False, "approved"),
        ("Lake-view 2BHK (awaiting approval)", "Apartment", "sale", 8900000, 2, 2, 1050, "Hebbal", "Bengaluru", "560024", True, "pending"),
    ]
    locations = [
        ("Indiranagar", "Bengaluru", "Karnataka", "560038"),
        ("Koramangala", "Bengaluru", "Karnataka", "560095"),
        ("Whitefield", "Bengaluru", "Karnataka", "560066"),
        ("HSR Layout", "Bengaluru", "Karnataka", "560102"),
        ("Jayanagar", "Bengaluru", "Karnataka", "560011"),
        ("Sarjapur Road", "Bengaluru", "Karnataka", "560035"),
        ("Hebbal", "Bengaluru", "Karnataka", "560024"),
        ("MG Road", "Bengaluru", "Karnataka", "560001"),
        ("Banashankari", "Bengaluru", "Karnataka", "560070"),
        ("Yelahanka", "Bengaluru", "Karnataka", "560064"),
    ]
    type_details = {
        "Apartment": ("Apartment home", 8500000, 28000, 1200, 2, 2, False),
        "House": ("Independent house", 14500000, 40000, 2100, 3, 2, False),
        "Villa": ("Garden villa", 26000000, 65000, 3000, 4, 4, False),
        "Studio": ("Studio home", 4200000, 18000, 500, 1, 1, True),
        "Plot": ("Residential plot", 7000000, 0, 2400, 0, 0, False),
        "Commercial": ("Commercial space", 18000000, 120000, 1900, 0, 2, False),
    }

    def add_listing(seller, amenities, record, image_index):
        (title, property_type, listing_type, price, bedrooms, bathrooms,
         area, address, city, state, pincode, furnished, status) = record
        prop = Property(
            owner_id=seller.id,
            title=title,
            description=(
                f"A well-maintained {property_type.lower()} in a convenient location "
                "with access to shops, schools and public transport. Contact the agent "
                "to arrange a visit."
            ),
            property_type=property_type,
            listing_type=listing_type,
            status=status,
            price=price,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            area=area,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
            is_furnished=furnished,
        )
        start = image_index % len(amenities)
        prop.amenities = amenities[start:start + 5]
        db.session.add(prop)
        db.session.flush()
        for offset, image_url in enumerate(PROPERTY_IMAGE_FILES[property_type]):
            db.session.add(PropertyImage(
                property_id=prop.id,
                image_url=image_url,
                is_main=(offset == 0),
            ))

    with app.app_context():
        users = {}
        for name, email, password, role, phone in users_data:
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(full_name=name, email=email, role=role, phone=phone)
                user.set_password(password)
                db.session.add(user)
            users[role] = user
        db.session.flush()
        amenities = Amenity.query.all()
        if not amenities:
            amenities = [Amenity(name=name) for name in DEFAULT_AMENITIES]
            db.session.add_all(amenities)
            db.session.flush()

        seller = users["seller"]
        for index, sample in enumerate(samples):
            if Property.query.filter_by(title=sample[0]).first() is None:
                add_listing(
                    seller, amenities,
                    (*sample[:9], "Karnataka", *sample[9:]),
                    index,
                )

        for property_type in PROPERTY_TYPES:
            (title_prefix, sale_price, rent_price, area, bedrooms,
             bathrooms, furnished) = type_details[property_type]
            count = Property.query.filter_by(
                property_type=property_type, status="approved"
            ).count()
            index = 1
            while count < 20:
                neighborhood, city, state, pincode = locations[(index - 1) % len(locations)]
                listing_type = "sale" if property_type == "Plot" or index % 2 else "rent"
                base_price = sale_price if listing_type == "sale" else rent_price
                price = int(base_price * (100 + (index % 7) * 5) / 100)
                title = f"{title_prefix} in {neighborhood} #{index:02d}"
                if Property.query.filter_by(title=title).first() is None:
                    add_listing(
                        seller, amenities,
                        (title, property_type, listing_type, price, bedrooms,
                         bathrooms, area + (index % 5) * 50,
                         f"Main Road, {neighborhood}", city, state, pincode,
                         furnished, "approved"),
                        index,
                    )
                    count += 1
                index += 1

        for prop in Property.query.all():
            image_files = PROPERTY_IMAGE_FILES[prop.property_type]
            for index, image in enumerate(prop.images):
                if image.image_url.startswith("images/placeholder"):
                    image.image_url = image_files[index % len(image_files)]

        db.session.commit()
        for property_type in PROPERTY_TYPES:
            count = Property.query.filter_by(
                property_type=property_type, status="approved"
            ).count()
            print(f"{property_type}: {count} approved listings")
        print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    if sys.argv[1:] == ["seed"]:
        seed_database()
    elif not sys.argv[1:]:
        app.run(debug=True)
    else:
        raise SystemExit("Usage: python app.py [seed]")
