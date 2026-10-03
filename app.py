"""ХААИС-ийн тоног төхөөрөмжийн бүртгэл — v5
Streamlit + SQLAlchemy + Supabase/Postgres.
"""
import hmac
import io
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import qrcode
import streamlit as st
from sqlalchemy import (Column, DateTime, Integer, MetaData, Numeric, String, Table,
                        Text, create_engine, delete, insert, inspect, select, text, update)

st.set_page_config(page_title="ХААИС | Тоног төхөөрөмж", page_icon="🏫", layout="wide")
LOGO_PATH = Path(__file__).parent / "assets" / "HAAIS.png"
STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]
ROLES = ["admin", "treasurer", "teacher", "viewer"]

st.markdown("""
<style>
:root{--green:#0b6b43;--green2:#138a58;--gold:#e7bd32;--ink:#17221d;--muted:#66756d;--bg:#f4f7f4;--card:#ffffff}
[data-testid="stAppViewContainer"]{background:var(--bg)} [data-testid="stHeader"]{background:transparent}
/* Streamlit branding болон дээд toolbar-ийг нуух */
footer{visibility:hidden} [data-testid="stToolbar"]{visibility:hidden} [data-testid="stDecoration"]{visibility:hidden}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#073f2b 0%,#0b6b43 58%,#075438 100%);border-right:0}
[data-testid="stSidebar"] *{color:#eef8f2!important}.block-container{max-width:1400px;padding:2rem 2.7rem 4rem}
.hero{padding:1.4rem 1.65rem;border:1px solid #dfe9e1;border-radius:22px;background:linear-gradient(120deg,#fff 0%,#f1f8f2 100%);box-shadow:0 10px 30px rgba(26,64,42,.06);margin-bottom:1.2rem}.hero-kicker,.section-label{color:var(--green);text-transform:uppercase;letter-spacing:.13em;font-size:.7rem;font-weight:800}.hero-title{color:var(--ink);font-size:2.1rem;font-weight:850;margin:.3rem 0}.hero-subtitle{color:var(--muted);margin:0}
.metric{background:var(--card);border:1px solid #e1ebe3;border-radius:18px;padding:1.15rem 1.2rem;min-height:108px;box-shadow:0 8px 22px rgba(26,64,42,.055)}.metric-label{color:#718078;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700}.metric-value{color:var(--green);font-size:1.8rem;font-weight:850;margin-top:.35rem}.metric-note{color:#ad8c13;font-size:.76rem;font-weight:650}
[data-testid="stForm"]{background:var(--card);border:1px solid #e1ebe3;border-radius:18px;padding:1.25rem;box-shadow:0 8px 22px rgba(26,64,42,.045)} [data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{border-radius:10px!important;background:#fbfdfb!important;border-color:#d8e5da!important}[data-testid="stDataFrame"]{border-radius:16px;overflow:hidden;border:1px solid #dce8de}
button[kind="primary"]{background:linear-gradient(135deg,var(--green2),var(--green))!important;border:0!important} .stButton>button{border-radius:10px}.nav-title{font-size:1.1rem;font-weight:800;letter-spacing:-.02em}.nav-caption{font-size:.72rem;opacity:.78;margin-bottom:1.2rem}.page-title{color:var(--ink);font-size:1.65rem;font-weight:850;margin:.2rem 0 .25rem}.page-caption{color:var(--muted);margin-bottom:1.25rem}.stRadio>div{gap:.28rem}.stRadio label{padding:.55rem .7rem;border-radius:9px}.stRadio label:hover{background:rgba(255,255,255,.12)}
@media(max-width:700px){.hero-title{font-size:1.55rem}.block-container{padding:1rem}.metric{min-height:92px}.metric-value{font-size:1.45rem}}
</style>
""", unsafe_allow_html=True)


def secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


def matches(value, expected):
    return bool(expected) and hmac.compare_digest(str(value).encode(), str(expected).encode())


def get_engine():
    url = secret("DATABASE_URL", "sqlite:///assets.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    # Existing database migration: add new fields without deleting old records.
    existing = {c["name"] for c in inspect(engine).get_columns("assets")}
    for name, sql_type in {
        "serial_number":"VARCHAR(120)", "purchase_date":"VARCHAR(30)", "purchase_price":"NUMERIC(14,2)",
        "warranty_until":"VARCHAR(30)", "image_url":"TEXT", "notes":"TEXT", "updated_at":"VARCHAR(30)"
    }.items():
        if name not in existing:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE assets ADD COLUMN {name} {sql_type}"))
    return engine


metadata = MetaData()
assets = Table("assets", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("name", String(200), nullable=False),
    Column("location", String(200), nullable=False), Column("quantity", Integer, nullable=False),
    Column("status", String(50), nullable=False), Column("created_at", String(30), nullable=False),
    Column("registered_by", String(100)), Column("serial_number", String(120)), Column("purchase_date", String(30)),
    Column("purchase_price", Numeric(14,2)), Column("warranty_until", String(30)), Column("image_url", Text),
    Column("notes", Text), Column("updated_at", String(30)))
repairs = Table("repairs", metadata, Column("id", Integer, primary_key=True), Column("asset_id", Integer), Column("issue", Text), Column("repair_date", String(30)), Column("completed_date", String(30)), Column("cost", Numeric(14,2)), Column("status", String(40)), Column("note", Text))
transfers = Table("transfers", metadata, Column("id", Integer, primary_key=True), Column("asset_id", Integer), Column("from_location", String(200)), Column("to_location", String(200)), Column("transfer_date", String(30)), Column("transferred_by", String(100)), Column("note", Text))
users = Table("users", metadata, Column("id", Integer, primary_key=True), Column("username", String(100), unique=True), Column("role", String(40)), Column("active", Integer, default=1))


def load_assets():
    with get_engine().connect() as conn:
        df = pd.read_sql_query(select(assets).order_by(assets.c.id.desc()), conn)
    for col in ["registered_by", "serial_number", "purchase_date", "warranty_until", "image_url", "notes", "updated_at"]:
        if col in df: df[col] = df[col].fillna("")
    return df


def asset_by_id(asset_id):
    with get_engine().connect() as conn:
        row = conn.execute(select(assets).where(assets.c.id == int(asset_id))).mappings().first()
    return dict(row) if row else None


def save_asset(values, asset_id=None):
    values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_engine().begin() as conn:
        if asset_id:
            conn.execute(update(assets).where(assets.c.id == int(asset_id)).values(**values))
        else:
            values["created_at"] = values.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
            conn.execute(insert(assets).values(**values))


def upload_image(uploaded):
    if not uploaded: return ""
    # Supabase Storage is optional; configure SUPABASE_URL, SUPABASE_KEY and ASSET_BUCKET.
    try:
        from supabase import create_client
        client = create_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"))
        bucket = secret("ASSET_BUCKET", "asset-images")
        path = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded.name}"
        client.storage.from_(bucket).upload(path, uploaded.getvalue(), {"content-type": uploaded.type, "upsert": "true"})
        return client.storage.from_(bucket).get_public_url(path)
    except Exception as exc:
        st.warning(f"Зураг хадгалах тохиргоо дутуу байна: {exc}")
        return ""


def qr_png(value):
    qr = qrcode.QRCode(box_size=12, border=4); qr.add_data(value); qr.make(fit=True)
    buf = io.BytesIO(); qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG"); return buf.getvalue()


def app_url(row):
    base = str(secret("APP_URL", "https://tonog-burtgel-9kpnaomprgjcdxjgbkhvc5.streamlit.app")).rstrip("/")
    return f"{base}/?id={row['id']}"


def require_login():
    role = st.session_state.get("role")
    if role: return role
    st.markdown("<div class='hero'><div class='hero-kicker'>ХААИС</div><div class='hero-title'>Нэвтрэх</div><p class='hero-subtitle'>Тоног төхөөрөмжийн бүртгэлийн систем</p></div>", unsafe_allow_html=True)
    with st.form("login"):
        password = st.text_input("Нууц үг", type="password")
        ok = st.form_submit_button("Нэвтрэх", type="primary", use_container_width=True)
    if ok:
        checks = [("admin", secret("APP_PASSWORD")), ("treasurer", secret("TREASURER_PASSWORD")), ("teacher", secret("TEACHER_PASSWORD")), ("viewer", secret("VIEWER_PASSWORD"))]
        for candidate, expected in checks:
            if matches(password, expected): st.session_state["role"] = candidate; st.rerun()
        st.error("Нууц үг буруу байна.")
    st.stop()


def header(role):
    with st.sidebar:
        if LOGO_PATH.exists(): st.image(str(LOGO_PATH), width=90)
        st.markdown("**ХААИС**  \nТоног төхөөрөмжийн систем")
        st.caption(f"Эрх: {role}")
        if st.button("Гарах", use_container_width=True): st.session_state.clear(); st.rerun()


def overview(df):
    total = int(df.quantity.sum()) if not df.empty else 0; healthy = int((df.status == "Хэвийн").sum()) if not df.empty else 0; attention = int(df.status.isin(["Засвартай","Эвдэрсэн"]).sum()) if not df.empty else 0
    cols = st.columns(4)
    cards = [("Нийт төрөл",len(df),"бүртгэл"),("Нийт тоо ширхэг",total,"тоног төхөөрөмж"),("Хэвийн төлөв",healthy,"төрөл"),("Анхаарах",attention,"засвар / эвдрэл")]
    for col,(label,value,note) in zip(cols,cards): col.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',unsafe_allow_html=True)


def add_form(role):
    if role not in ROLES[:3]: st.info("Танд шинэ бүртгэл нэмэх эрх байхгүй."); return
    st.markdown('<div class="section-label">Шинэ тоног төхөөрөмж</div>', unsafe_allow_html=True)
    with st.form("add_asset", clear_on_submit=True):
        a,b = st.columns(2); name = a.text_input("Нэр *", placeholder="Проектор"); location = b.text_input("Байршил *", placeholder="12А анги")
        c,d = st.columns(2); serial = c.text_input("Серийн дугаар"); quantity = d.number_input("Тоо ширхэг",1,10000,1)
        e,f = st.columns(2); status = e.selectbox("Төлөв", STATUSES); registered = f.text_input("Бүртгэсэн багш")
        g,h = st.columns(2); purchase_date = g.date_input("Худалдан авсан огноо", value=None); warranty = h.date_input("Баталгаат хугацаа дуусах", value=None)
        i,j = st.columns(2); price = i.number_input("Үнэ (₮)", min_value=0.0, step=1000.0); image = j.file_uploader("Зураг", type=["png","jpg","jpeg"])
        notes = st.text_area("Тайлбар"); submitted = st.form_submit_button("＋ Бүртгэх", type="primary", use_container_width=True)
    if submitted:
        if not name.strip() or not location.strip(): st.error("Нэр болон байршлыг заавал бөглөнө үү."); return
        image_url = upload_image(image)
        save_asset(dict(name=name.strip(),location=location.strip(),quantity=int(quantity),status=status,registered_by=registered.strip(),serial_number=serial.strip(),purchase_date=str(purchase_date) if purchase_date else "",warranty_until=str(warranty) if warranty else "",purchase_price=float(price),image_url=image_url,notes=notes.strip()))
        st.success(f"✅ {name} амжилттай бүртгэгдлээ."); st.rerun()


def list_view(df):
    if df.empty: st.info("Одоогоор бүртгэл алга."); return
    a,b,c = st.columns([2,1,1]); query = a.text_input("🔍 Нэр, серийн дугаар, байршил хайх"); statuses = b.multiselect("Төлөв", STATUSES); locations = c.multiselect("Байршил", sorted(df.location.dropna().unique()))
    view=df.copy(); query=query.lower().strip()
    if query: view=view[view.apply(lambda r: query in f"{r.name} {r.location} {r.serial_number} {r.registered_by}".lower(),axis=1)]
    if statuses: view=view[view.status.isin(statuses)]
    if locations: view=view[view.location.isin(locations)]
    cols={"id":"ID","name":"Нэр","serial_number":"Серийн дугаар","location":"Байршил","quantity":"Тоо","status":"Төлөв","purchase_price":"Үнэ","registered_by":"Бүртгэсэн"}
    st.dataframe(view[[c for c in cols if c in view]].rename(columns=cols), hide_index=True, use_container_width=True)
    st.caption(f"{len(view)} бичлэг · {int(view.quantity.sum())} ширхэг")


def edit_view(df, role):
    if role not in ["admin","treasurer"]: st.info("Зөвхөн админ болон нярав засварлана."); return
    if df.empty: st.info("Засах бүртгэл алга."); return
    opts={f"#{r.id} — {r['name']} ({r['location']})":int(r.id) for _,r in df.iterrows()}; choice=st.selectbox("Тоног төхөөрөмж сонгох",list(opts)); row=asset_by_id(opts[choice]); rid=int(row["id"])
    with st.form(f"edit_{rid}"):
        a,b=st.columns(2); name=a.text_input("Нэр",row["name"]); location=b.text_input("Байршил",row["location"]); c,d=st.columns(2); serial=c.text_input("Серийн дугаар",row.get("serial_number") or ""); status=d.selectbox("Төлөв",STATUSES,index=STATUSES.index(row["status"]) if row["status"] in STATUSES else 0); by=st.text_input("Бүртгэсэн багш",row.get("registered_by") or ""); notes=st.text_area("Тайлбар",row.get("notes") or ""); save=st.form_submit_button("💾 Хадгалах",type="primary")
    if save: save_asset(dict(name=name.strip(),location=location.strip(),quantity=int(row["quantity"]),status=status,registered_by=by.strip(),serial_number=serial.strip(),notes=notes.strip()),rid); st.success("Шинэчлэгдлээ."); st.rerun()
    if st.checkbox("Устгахыг зөвшөөрч байна",key=f"confirm{rid}") and st.button("🗑 Устгах",key=f"delete{rid}"):
        with get_engine().begin() as conn: conn.execute(delete(assets).where(assets.c.id==rid))
        st.rerun()


def repairs_view(df, role):
    if df.empty: st.info("Эхлээд тоног төхөөрөмж бүртгэнэ үү."); return
    opts={f"#{r.id} — {r['name']}":int(r.id) for _,r in df.iterrows()}; choice=st.selectbox("Төхөөрөмж",list(opts),key="repair_asset"); aid=opts[choice]
    with st.form("repair_form"):
        issue=st.text_input("Гэмтэл / асуудал *"); rd=st.date_input("Засварт өгсөн огноо"); cost=st.number_input("Зардал (₮)",0.0,step=1000.0); status=st.selectbox("Засварын төлөв",["Хүлээгдэж буй","Засвартай","Дууссан"]); note=st.text_area("Тайлбар"); ok=st.form_submit_button("Засварын түүх нэмэх",type="primary")
    if ok and issue.strip():
        with get_engine().begin() as conn: conn.execute(insert(repairs).values(asset_id=aid,issue=issue.strip(),repair_date=str(rd),cost=cost,status=status,note=note.strip()))
        st.success("Засварын түүх нэмэгдлээ.")
    with get_engine().connect() as conn: history=pd.read_sql_query(select(repairs).where(repairs.c.asset_id==aid).order_by(repairs.c.id.desc()),conn)
    if not history.empty: st.dataframe(history,hide_index=True,use_container_width=True)


def transfer_view(df, role):
    if role not in ["admin","treasurer","teacher"]: st.info("Танд шилжүүлэг хийх эрх байхгүй."); return
    if df.empty: st.info("Бүртгэл алга."); return
    opts={f"#{r.id} — {r['name']} ({r['location']})":r for _,r in df.iterrows()}; choice=st.selectbox("Төхөөрөмж",list(opts),key="transfer_asset"); row=opts[choice]
    with st.form("transfer_form"):
        to=st.text_input("Шинэ байршил *"); td=st.date_input("Шилжүүлсэн огноо"); by=st.text_input("Шилжүүлсэн хүн"); note=st.text_area("Тайлбар"); ok=st.form_submit_button("Шилжүүлэг хадгалах",type="primary")
    if ok and to.strip():
        with get_engine().begin() as conn: conn.execute(insert(transfers).values(asset_id=int(row.id),from_location=row.location,to_location=to.strip(),transfer_date=str(td),transferred_by=by.strip(),note=note.strip())); conn.execute(update(assets).where(assets.c.id==int(row.id)).values(location=to.strip(),updated_at=datetime.now().strftime("%Y-%m-%d %H:%M")))
        st.success("Байршил шинэчлэгдлээ."); st.rerun()
    with get_engine().connect() as conn: history=pd.read_sql_query(select(transfers).where(transfers.c.asset_id==int(row.id)).order_by(transfers.c.id.desc()),conn)
    if not history.empty: st.dataframe(history,hide_index=True,use_container_width=True)


def reports_view(df):
    st.subheader("Тайлан татах")
    c1,c2=st.columns(2)
    with c1:
        xlsx=io.BytesIO()
        with pd.ExcelWriter(xlsx,engine="openpyxl") as writer: df.to_excel(writer,index=False,sheet_name="Тоног төхөөрөмж")
        st.download_button("⬇ Excel татах",xlsx.getvalue(),"tonog_tuhuurumj.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    with c2:
        st.download_button("⬇ CSV татах",df.to_csv(index=False).encode("utf-8-sig"),"tonog_tuhuurumj.csv","text/csv",use_container_width=True)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        pdf=io.BytesIO(); p=canvas.Canvas(pdf,pagesize=A4); p.setFont("Helvetica-Bold",16); p.drawString(50,800,"ХААИС - Тоног төхөөрөмжийн тайлан"); p.setFont("Helvetica",10); y=775
        for _,r in df.head(35).iterrows(): p.drawString(50,y,f"#{r.id} {r['name']} | {r['location']} | {r['status']} | тоо: {r['quantity']}"); y-=16
        p.save(); st.download_button("⬇ PDF татах",pdf.getvalue(),"tonog_tuhuurumj.pdf","application/pdf",use_container_width=True)
    except ImportError: st.info("PDF-д requirements.txt дотор reportlab нэмнэ үү.")


def charts_view(df):
    if df.empty: st.info("График харуулах өгөгдөл алга."); return
    try:
        import plotly.express as px
        a,b=st.columns(2); a.plotly_chart(px.bar(df.groupby("status",as_index=False).quantity.sum(),x="status",y="quantity",color="status",title="Төлвөөр тоо ширхэг"),use_container_width=True); b.plotly_chart(px.bar(df.groupby("location",as_index=False).quantity.sum().sort_values("quantity",ascending=False).head(12),x="location",y="quantity",title="Байршлаар"),use_container_width=True)
    except ImportError: st.info("Графикт requirements.txt дотор plotly нэмнэ үү.")


role = require_login()
df = load_assets()

# Sidebar navigation — өгөгдлийн логик өөрчлөгдөөгүй, зөвхөн UI-ийн navigation.
with st.sidebar:
    st.markdown('<div class="nav-title">◈  ХААИС</div><div class="nav-caption">Тоног төхөөрөмжийн систем</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="nav-caption">ҮНДСЭН ЦЭС</div>', unsafe_allow_html=True)
    if role == "admin":
        pages = ["⌂  Dashboard", "＋  Бүртгэх", "▦  Тоног төхөөрөмж", "✎  Удирдах", "⚒  Засвар", "↔  Шилжүүлэг", "▣  QR төв", "⇩  Тайлан"]
    elif role in ["treasurer", "teacher"]:
        pages = ["⌂  Dashboard", "＋  Бүртгэх", "▦  Тоног төхөөрөмж", "⚒  Засвар", "↔  Шилжүүлэг", "▣  QR төв", "⇩  Тайлан"]
    else:
        pages = ["⌂  Dashboard", "▦  Тоног төхөөрөмж", "▣  QR төв"]
    page = st.radio("Цэс", pages, label_visibility="collapsed", key="main_nav")
    st.markdown("---")
    st.caption(f"Нэвтэрсэн эрх: {role.upper()}")
    if st.button("⎋  Гарах", use_container_width=True):
        st.session_state.clear(); st.rerun()

# Top bar and brand header.
top_left, top_right = st.columns([7, 1])
with top_left:
    st.markdown('<div class="page-title">Тоног төхөөрөмжийн бүртгэл</div><div class="page-caption">ХААИС-ийн хөрөнгө удирдлагын нэгдсэн систем</div>', unsafe_allow_html=True)
with top_right:
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), width=58)

if page == "⌂  Dashboard":
    st.markdown('<div class="hero"><div class="hero-kicker">School asset management</div><div class="hero-title">Сайн байна уу, системийн хэрэглэгч</div><p class="hero-subtitle">Өнөөдрийн тоног төхөөрөмжийн бүртгэл, төлөв, үйл ажиллагааг нэг дороос хянаарай.</p></div>', unsafe_allow_html=True)
    overview(df)
    st.markdown("### Төлөвийн тойм")
    charts_view(df)
    if not df.empty:
        st.markdown("### Сүүлийн бүртгэлүүд")
        recent = df.head(5)[["id","name","location","status","quantity","updated_at"]].rename(columns={"id":"ID","name":"Нэр","location":"Байршил","status":"Төлөв","quantity":"Тоо","updated_at":"Шинэчилсэн"})
        st.dataframe(recent, hide_index=True, use_container_width=True)
elif page == "＋  Бүртгэх":
    st.markdown('<div class="hero"><div class="hero-kicker">Asset registration</div><div class="hero-title">Шинэ тоног төхөөрөмж бүртгэх</div><p class="hero-subtitle">Шаардлагатай мэдээллийг бөглөж, зургийг хавсаргана уу.</p></div>', unsafe_allow_html=True)
    add_form(role)
elif page == "▦  Тоног төхөөрөмж":
    st.markdown('<div class="hero"><div class="hero-kicker">Inventory</div><div class="hero-title">Тоног төхөөрөмжийн жагсаалт</div><p class="hero-subtitle">Хайх, шүүх, бүртгэлүүдээ хянах.</p></div>', unsafe_allow_html=True)
    list_view(df)
elif page == "✎  Удирдах":
    st.markdown('<div class="hero"><div class="hero-kicker">Manage assets</div><div class="hero-title">Бүртгэл удирдах</div><p class="hero-subtitle">Мэдээлэл засах эсвэл хуучирсан бүртгэлийг устгах.</p></div>', unsafe_allow_html=True)
    edit_view(df, role)
elif page == "⚒  Засвар":
    st.markdown('<div class="hero"><div class="hero-kicker">Maintenance</div><div class="hero-title">Засвар үйлчилгээ</div><p class="hero-subtitle">Засварын түүх болон зардлыг бүртгэх.</p></div>', unsafe_allow_html=True)
    repairs_view(df, role)
elif page == "↔  Шилжүүлэг":
    st.markdown('<div class="hero"><div class="hero-kicker">Transfers</div><div class="hero-title">Байршил шилжүүлэг</div><p class="hero-subtitle">Төхөөрөмжийн одоогийн байршил болон шилжилтийн түүх.</p></div>', unsafe_allow_html=True)
    transfer_view(df, role)
elif page == "⇩  Тайлан":
    st.markdown('<div class="hero"><div class="hero-kicker">Reports</div><div class="hero-title">Тайлан татах</div><p class="hero-subtitle">Бүртгэлийн өгөгдлийг Excel, CSV эсвэл PDF хэлбэрээр татах.</p></div>', unsafe_allow_html=True)
    reports_view(df)
elif page == "▣  QR төв":
    st.markdown('<div class="hero"><div class="hero-kicker">QR center</div><div class="hero-title">QR кодын төв</div><p class="hero-subtitle">Төхөөрөмжийн шошго үүсгэх, татах, камераар шалгах.</p></div>', unsafe_allow_html=True)
    if df.empty: st.info("QR үүсгэхийн тулд эхлээд бүртгэл нэмнэ үү.")
    else:
        opts={f"#{r.id} — {r['name']} ({r['location']})":r for _,r in df.iterrows()}; choice=st.selectbox("Төхөөрөмж сонгох",list(opts),key="qr_asset"); row=opts[choice]; payload=app_url(row); png=qr_png(payload)
        a,b=st.columns([1,2]); a.image(png,width=270); b.markdown(f"### {row['name']}\n\n**ID:** #{row['id']}  \n**Байршил:** {row['location']}  \n**Төлөв:** {row['status']}"); b.download_button("⬇ QR татах",png,f"asset_{row['id']}_qr.png","image/png",use_container_width=True)
        st.markdown("### Камераар шалгах")
        camera=st.camera_input("Камер нээх",key="qr_camera")
        if camera:
            try:
                import cv2, numpy as np
                value,_,_=cv2.QRCodeDetector().detectAndDecode(cv2.imdecode(np.frombuffer(camera.getvalue(),np.uint8),cv2.IMREAD_COLOR))
                if value: st.success(f"QR холбоос: {value}")
                else: st.warning("QR код танигдсангүй. Камераа ойртуулж дахин оролдоно уу.")
            except ImportError: st.info("QR camera-д opencv-python-headless шаардлагатай.")
