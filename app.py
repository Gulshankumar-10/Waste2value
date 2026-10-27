import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.abspath(os.path.dirname(__file__))
DB = os.path.join(ROOT, "waste2value.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-secret-before-production")
MATERIALS = ["Plastic", "Metal", "Cardboard", "Paper", "Glass", "E-waste", "Textile", "Other"]
CONDITIONS = ["Sorted", "Mixed", "Cleaned", "Processed"]

def conn():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, organisation TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY, title TEXT NOT NULL, material TEXT NOT NULL, description TEXT DEFAULT '', quantity REAL NOT NULL, unit TEXT NOT NULL, rate REAL NOT NULL, location TEXT NOT NULL, condition TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available', created_at TEXT NOT NULL, created_by INTEGER);
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL, buyer_id INTEGER NOT NULL, quantity REAL NOT NULL, message TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(listing_id) REFERENCES listings(id), FOREIGN KEY(buyer_id) REFERENCES users(id));
    """)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users(name,email,password_hash,role,organisation) VALUES(?,?,?,?,?)",
                   ("Waste2Value Admin","admin@waste2value.local",generate_password_hash("Admin@123"),"admin","Recovery Operations"))
        db.execute("INSERT INTO users(name,email,password_hash,role,organisation) VALUES(?,?,?,?,?)",
                   ("Demo Buyer","buyer@waste2value.local",generate_password_hash("Buyer@123"),"buyer","Circular Materials Co."))
        aid = db.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        samples = [
          ("Sorted HDPE flakes","Plastic","Washed HDPE flakes for recycling trials.",850,"kg",42,"Greater Noida","Cleaned"),
          ("Aluminium offcuts","Metal","Dry aluminium offcuts from light fabrication.",320,"kg",118,"Ghaziabad","Sorted"),
          ("Corrugated cardboard bales","Cardboard","Flattened and tied corrugated packaging.",1200,"kg",16,"Noida","Sorted"),
          ("Office paper surplus","Paper","Mixed office paper kept dry in covered storage.",475,"kg",13,"Faridabad","Mixed"),
          ("Clear glass cullet","Glass","Separated clear glass fragments; handle with care.",260,"kg",8,"Delhi NCR","Processed"),
          ("Cotton textile offcuts","Textile","Clean cotton cutting waste in reusable sacks.",190,"kg",21,"Greater Noida","Sorted")]
        db.executemany("INSERT INTO listings(title,material,description,quantity,unit,rate,location,condition,status,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       [(t,m,d,q,u,r,l,c,"available",now,aid) for t,m,d,q,u,r,l,c in samples])
    db.commit(); db.close()
init_db()

def login_required(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        if not session.get("user_id"):
            flash("Sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return fn(*a, **kw)
    return wrap

def role_required(role):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            if not session.get("user_id"): return redirect(url_for("login"))
            if session.get("role") != role: abort(403)
            return fn(*a, **kw)
        return wrap
    return deco

@app.context_processor
def globals_for_templates():
    return {"current_user":session.get("user_name"), "current_role":session.get("role")}

@app.route("/")
def index():
    db=conn()
    stats={"materials":db.execute("SELECT COUNT(*) FROM listings WHERE status='available' AND quantity>0").fetchone()[0],
           "quantity":db.execute("SELECT COALESCE(SUM(quantity),0) FROM listings WHERE status='available'").fetchone()[0],
           "categories":db.execute("SELECT COUNT(DISTINCT material) FROM listings WHERE status='available'").fetchone()[0]}
    featured=db.execute("SELECT * FROM listings WHERE status='available' AND quantity>0 ORDER BY id DESC LIMIT 3").fetchall()
    return render_template("index.html",stats=stats,featured=featured)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        user=conn().execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password_hash"],request.form.get("password","")):
            session.clear(); session.update(user_id=user["id"],user_name=user["name"],role=user["role"],organisation=user["organisation"])
            flash("Welcome back, "+user["name"].split()[0]+".","success")
            nxt=request.args.get("next","")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Email or password did not match.","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("Signed out.","info"); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    db=conn()
    if session["role"]=="admin":
        total=db.execute("SELECT COUNT(*) FROM listings WHERE status='available' AND quantity>0").fetchone()[0]
        qty=db.execute("SELECT COALESCE(SUM(quantity),0) FROM listings WHERE status='available'").fetchone()[0]
        pending=db.execute("SELECT COUNT(*) FROM requests WHERE status='pending'").fetchone()[0]
        value=db.execute("SELECT COALESCE(SUM(quantity*rate),0) FROM listings WHERE status='available'").fetchone()[0]
        reqs=db.execute("SELECT r.*,l.title,u.name buyer_name FROM requests r JOIN listings l ON l.id=r.listing_id JOIN users u ON u.id=r.buyer_id ORDER BY r.id DESC LIMIT 6").fetchall()
        items=db.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 5").fetchall()
        return render_template("admin.html",total=total,qty=qty,pending=pending,value=value,reqs=reqs,items=items)
    reqs=db.execute("SELECT r.*,l.title,l.material,l.unit,l.rate FROM requests r JOIN listings l ON l.id=r.listing_id WHERE r.buyer_id=? ORDER BY r.id DESC",(session["user_id"],)).fetchall()
    count=db.execute("SELECT COUNT(*) FROM requests WHERE buyer_id=?",(session["user_id"],)).fetchone()[0]
    pending=db.execute("SELECT COUNT(*) FROM requests WHERE buyer_id=? AND status='pending'",(session["user_id"],)).fetchone()[0]
    return render_template("buyer.html",reqs=reqs,count=count,pending=pending)

@app.route("/marketplace")
def marketplace():
    q=request.args.get("q","").strip(); mat=request.args.get("material",""); cond=request.args.get("condition","")
    sql="SELECT * FROM listings WHERE status='available' AND quantity>0"; args=[]
    if q: sql+=" AND (title LIKE ? OR description LIKE ? OR location LIKE ?)"; args += [f"%{q}%"]*3
    if mat in MATERIALS: sql+=" AND material=?"; args.append(mat)
    if cond in CONDITIONS: sql+=" AND condition=?"; args.append(cond)
    sql+=" ORDER BY id DESC"
    rows=conn().execute(sql,args).fetchall()
    return render_template("marketplace.html",listings=rows,materials=MATERIALS,conditions=CONDITIONS,q=q,mat=mat,cond=cond)

@app.route("/listing/new",methods=["GET","POST"])
@role_required("admin")
def new_listing():
    if request.method=="POST":
        title=request.form.get("title","").strip(); material=request.form.get("material","")
        desc=request.form.get("description","").strip(); location=request.form.get("location","").strip()
        condition=request.form.get("condition","Sorted"); unit=request.form.get("unit","kg")
        try: qty=float(request.form.get("quantity","0")); rate=float(request.form.get("rate","-1"))
        except ValueError: qty,rate=0,-1
        if not title or material not in MATERIALS or condition not in CONDITIONS or not location or unit not in ("kg","tonne") or qty<=0 or rate<0:
            flash("Check all required fields and enter a positive quantity and non-negative rate.","error")
            return render_template("listing_form.html",materials=MATERIALS,conditions=CONDITIONS)
        conn().execute("INSERT INTO listings(title,material,description,quantity,unit,rate,location,condition,status,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (title,material,desc,qty,unit,rate,location,condition,"available",datetime.now().strftime("%Y-%m-%d %H:%M"),session["user_id"]))
        conn().commit(); flash("Material listing published.","success"); return redirect(url_for("marketplace"))
    return render_template("listing_form.html",materials=MATERIALS,conditions=CONDITIONS)

@app.route("/listing/<int:lid>")
def detail(lid):
    item=conn().execute("SELECT * FROM listings WHERE id=?",(lid,)).fetchone()
    if not item: abort(404)
    return render_template("detail.html",item=item)

@app.route("/listing/<int:lid>/request",methods=["POST"])
@role_required("buyer")
def create_request(lid):
    db=conn(); item=db.execute("SELECT * FROM listings WHERE id=?",(lid,)).fetchone()
    if not item or item["status"]!="available" or item["quantity"]<=0:
        flash("This material is no longer available.","error"); return redirect(url_for("marketplace"))
    try: qty=float(request.form.get("quantity","0"))
    except ValueError: qty=0
    if qty<=0 or qty>item["quantity"]:
        flash(f"Quantity must be greater than zero and no more than {item['quantity']:g} {item['unit']}.","error")
        return redirect(url_for("detail",lid=lid))
    now=datetime.now().strftime("%Y-%m-%d %H:%M")
    db.execute("INSERT INTO requests(listing_id,buyer_id,quantity,message,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
       (lid,session["user_id"],qty,request.form.get("message","").strip()[:500],"pending",now,now))
    db.commit(); flash("Request sent to the recovery team.","success"); return redirect(url_for("dashboard"))

@app.route("/requests")
@login_required
def requests_page():
    db=conn()
    sql="""SELECT r.*,l.title,l.material,l.unit,l.rate,u.name buyer_name,u.organisation FROM requests r
           JOIN listings l ON l.id=r.listing_id JOIN users u ON u.id=r.buyer_id"""
    args=()
    if session["role"]!="admin": sql+=" WHERE r.buyer_id=?"; args=(session["user_id"],)
    rows=db.execute(sql+" ORDER BY r.id DESC",args).fetchall()
    return render_template("requests.html",requests=rows)

@app.route("/requests/<int:rid>/<action>",methods=["POST"])
@role_required("admin")
def update_request(rid,action):
    if action not in ("approve","reject"): abort(404)
    db=conn()
    r=db.execute("SELECT r.*,l.quantity stock,l.status listing_status,l.id lid FROM requests r JOIN listings l ON l.id=r.listing_id WHERE r.id=?",(rid,)).fetchone()
    if not r: abort(404)
    if r["status"]!="pending": flash("Only pending requests can be updated.","error"); return redirect(url_for("requests_page"))
    now=datetime.now().strftime("%Y-%m-%d %H:%M")
    if action=="approve":
        if r["listing_status"]!="available" or r["quantity"]>r["stock"]:
            flash("Not enough stock is available to approve this request.","error"); return redirect(url_for("requests_page"))
        remaining=r["stock"]-r["quantity"]
        db.execute("UPDATE listings SET quantity=?,status=? WHERE id=?",(remaining,"available" if remaining>0 else "sold_out",r["lid"]))
        db.execute("UPDATE requests SET status='approved',updated_at=? WHERE id=?",(now,rid))
        flash("Request approved; stock has been updated.","success")
    else:
        db.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?",(now,rid)); flash("Request rejected.","info")
    db.commit(); return redirect(url_for("requests_page"))

@app.errorhandler(403)
def forbidden(e): return render_template("error.html",code=403,title="Not permitted",message="This area is not available for your account."),403
@app.errorhandler(404)
def missing(e): return render_template("error.html",code=404,title="Page not found",message="The link may be incorrect or the listing no longer exists."),404

if __name__=="__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG")=="1")
