import os, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "atelier.db"))
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
db = SQLAlchemy(app)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, default="")

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.String(80), default="يحدد بعد المعاينة")
    active = db.Column(db.Boolean, default=True)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), default="")
    filename = db.Column(db.String(255), nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    service = db.Column(db.String(140), nullable=False)
    visit_date = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Integer, default=5)
    message = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, default=False)

class CustomRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    details = db.Column(db.String(200), default="")
    active = db.Column(db.Boolean, default=True)

class GiftRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.String(40), default="")
    note = db.Column(db.Text, default="")

def setting(key, default=""):
    item = Setting.query.filter_by(key=key).first()
    return item.value if item else default

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_settings():
    return {"shop_name": setting("shop_name", "ATELIER QUEEN"), "phone": setting("phone", "01229444018"),
            "address": setting("address", "شارع الرحمة، أمام مكتبة أبو عصام، خورشيد البحرية، الإسكندرية"),
            "hours": setting("hours", "يوميًا من 10 صباحًا حتى 5 فجرًا")}

@app.route("/")
def home():
    return render_template("home.html", services=Service.query.filter_by(active=True).all(),
                           photos=Photo.query.order_by(Photo.id.desc()).all(),
                           reviews=Review.query.filter_by(approved=True).order_by(Review.id.desc()).all())

@app.route("/book", methods=["POST"])
def book():
    name, phone, service = (request.form.get(x, "").strip() for x in ("name", "phone", "service"))
    if not all([name, phone, service]):
        flash("اكتب الاسم ورقم الهاتف واختار الخدمة.")
        return redirect(url_for("home"))
    code = "AQ" + secrets.token_hex(3).upper()
    db.session.add(Booking(code=code, name=name, phone=phone, service=service,
                           visit_date=request.form.get("visit_date",""), notes=request.form.get("notes","")))
    db.session.commit()
    flash("تم استلام طلب الحجز. رقم الحجز: " + code)
    return redirect(url_for("home"))

@app.route("/custom", methods=["POST"])
def custom():
    name, phone, details = (request.form.get(x, "").strip() for x in ("name", "phone", "details"))
    if not all([name, phone, details]):
        flash("اكتب الاسم ورقم الهاتف وتفاصيل التصميم.")
        return redirect(url_for("home"))
    image_name = ""
    f = request.files.get("reference")
    if f and f.filename:
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            flash("الصورة لازم تكون JPG أو PNG أو WEBP.")
            return redirect(url_for("home"))
        image_name = secrets.token_hex(12) + ext
        f.save(os.path.join(UPLOAD_DIR, image_name))
    db.session.add(CustomRequest(name=name, phone=phone, details=details, image=image_name))
    db.session.commit()
    flash("تم إرسال طلب التصميم بنجاح.")
    return redirect(url_for("home"))

@app.route("/review", methods=["POST"])
def review():
    name, message = request.form.get("name","").strip(), request.form.get("message","").strip()
    if name and message:
        db.session.add(Review(name=name, message=message, rating=max(1,min(5,int(request.form.get("rating",5))))))
        db.session.commit()
        flash("شكرًا لتقييمك. سيظهر بعد المراجعة.")
    return redirect(url_for("home"))

@app.route("/gift", methods=["POST"])
def gift():
    name, phone = request.form.get("name","").strip(), request.form.get("phone","").strip()
    if name and phone:
        db.session.add(GiftRequest(name=name, phone=phone, amount=request.form.get("amount",""), note=request.form.get("note","")))
        db.session.commit()
        flash("تم استلام طلب كارت الهدية.")
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
        password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
        entered = request.form.get("password","")
        if request.form.get("username","") == username and ((password_hash and check_password_hash(password_hash, entered)) or (not password_hash and secrets.compare_digest(entered, password))):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("بيانات الدخول غير صحيحة.")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", bookings=Booking.query.order_by(Booking.id.desc()).all(),
        custom=CustomRequest.query.order_by(CustomRequest.id.desc()).all(),
        gifts=GiftRequest.query.order_by(GiftRequest.id.desc()).all(),
        reviews=Review.query.order_by(Review.id.desc()).all(),
        services=Service.query.order_by(Service.id.desc()).all(),
        photos=Photo.query.order_by(Photo.id.desc()).all(),
        coupons=Coupon.query.order_by(Coupon.id.desc()).all())

@app.route("/admin/service", methods=["POST"])
@admin_required
def add_service():
    title=request.form.get("title","").strip()
    if title:
        db.session.add(Service(title=title, description=request.form.get("description",""), price=request.form.get("price","")))
        db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/service/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_service(item_id):
    item= db.session.get(Service,item_id)
    if item: db.session.delete(item); db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/photo", methods=["POST"])
@admin_required
def add_photo():
    f=request.files.get("photo")
    if f and f.filename:
        ext=os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in [".jpg",".jpeg",".png",".webp"]:
            flash("ارفع صورة JPG أو PNG أو WEBP.")
        else:
            name=secrets.token_hex(12)+ext
            f.save(os.path.join(UPLOAD_DIR,name))
            db.session.add(Photo(title=request.form.get("title",""),filename=name)); db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/photo/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_photo(item_id):
    item=db.session.get(Photo,item_id)
    if item:
        try: os.remove(os.path.join(UPLOAD_DIR,item.filename))
        except OSError: pass
        db.session.delete(item); db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/review/<int:item_id>/approve", methods=["POST"])
@admin_required
def approve_review(item_id):
    item=db.session.get(Review,item_id)
    if item: item.approved=True; db.session.commit()
    return redirect(url_for("admin"))

@app.route("/admin/coupon", methods=["POST"])
@admin_required
def add_coupon():
    code=request.form.get("code","").strip().upper()
    if code and not Coupon.query.filter_by(code=code).first():
        db.session.add(Coupon(code=code,details=request.form.get("details",""))); db.session.commit()
    return redirect(url_for("admin"))

@app.route("/health")
def health():
    return {"status":"ok"}

with app.app_context():
    db.create_all()
    if not Service.query.first():
        db.session.add_all([
            Service(title="تفصيل جميع أنواع الملابس",description="تفصيل حسب المقاس والطلب.",price="يحدد بعد المعاينة"),
            Service(title="تعديل وإصلاح الملابس",description="تضييق وتوسيع وإصلاح مختلف أنواع الملابس.",price="يحدد بعد المعاينة"),
            Service(title="صيانة ماكينات الخياطة",description="صيانة وإصلاح الماكينات القديمة والجديدة داخل الأتيليه فقط.",price="يحدد بعد المعاينة")
        ])
        db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
