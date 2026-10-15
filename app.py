"""ХААИС-ийн тоног төхөөрөмжийн бүртгэл — v6
Streamlit + SQLAlchemy + Supabase/Postgres.
"""
import base64
import hmac
import html
import io
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs

import pandas as pd
import qrcode
import streamlit as st
from sqlalchemy import (Column, DateTime, Integer, MetaData, Numeric, String, Table,
                        Text, create_engine, delete, insert, inspect, select, text, update)

SCHOOL_LOGO_B64 = "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"  # сургуулийн лого (PNG, base64)
SCHOOL_LOGO_BYTES = base64.b64decode(SCHOOL_LOGO_B64)


def _favicon():
    try:
        from PIL import Image
        return Image.open(io.BytesIO(base64.b64decode(SCHOOL_LOGO_B64)))
    except Exception:
        return "🏫"


st.set_page_config(page_title="ХААИС | Тоног төхөөрөмж", page_icon=_favicon(), layout="wide")
STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]
ROLES = ["admin", "treasurer", "teacher", "viewer"]

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#1fa36c"/>
<stop offset=".55" stop-color="#0b6b43"/>
<stop offset="1" stop-color="#06402a"/>
</linearGradient>
<linearGradient id="top" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#f7de78"/>
<stop offset="1" stop-color="#e7bd32"/>
</linearGradient>
</defs>
<rect x="4" y="4" width="112" height="112" rx="28" fill="url(#bg)"/>
<rect x="4" y="4" width="112" height="112" rx="28" fill="none" stroke="#ffffff" stroke-opacity=".18" stroke-width="1.5"/>
<g stroke="#0b6b43" stroke-width="2" stroke-linejoin="round">
<polygon points="60,26 90,43 60,60 30,43" fill="url(#top)"/>
<polygon points="30,43 60,60 60,94 30,77" fill="#ffffff"/>
<polygon points="60,60 90,43 90,77 60,94" fill="#cfe9da"/>
</g>
<g fill="#0b6b43" opacity=".85">
<polygon points="36,53 47,59.4 47,64.4 36,58"/>
<polygon points="36,63 47,69.4 47,72.4 36,66"/>
</g>
<path d="M45 35 L60 43.5 L75 35" fill="none" stroke="#0b6b43" stroke-opacity=".35" stroke-width="1.5" stroke-linejoin="round"/>
<circle cx="90" cy="90" r="17" fill="#e7bd32" stroke="#0b6b43" stroke-width="3"/>
<path d="M82 90.5 L88 96.5 L99 84" fill="none" stroke="#0b6b43" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def logo_html(size=64):
    b64 = base64.b64encode(LOGO_SVG.encode("utf-8")).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{size}" height="{size}" style="display:block">'


def show_logos(size=64, container=st):
    """Сургуулийн лого (PNG) болон системийн лого (SVG) хоёрыг зэрэгцүүлж харуулна."""
    c1, c2 = container.columns([1, 1])
    c1.image(SCHOOL_LOGO_BYTES, width=size)
    c2.markdown(logo_html(size), unsafe_allow_html=True)


st.markdown("""
<style>
:root{--green:#0b6b43;--green2:#138a58;--gold:#e7bd32;--ink:#17221d;--muted:#66756d;--bg:#f4f7f4;--card:#ffffff}
[data-testid="stAppViewContainer"]{background:var(--bg)} [data-testid="stHeader"]{background:transparent}
/* Streamlit branding болон дээд toolbar-ийг нуух */
footer, footer *{display:none!important;visibility:hidden!important;height:0!important;min-height:0!important}
/* Toolbar болон Streamlit-ийн dark/light mode цэсийг хэвээр үлдээнэ */
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
    _lc, _ = st.columns([1, 2])
    show_logos(80, _lc)
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
    if query: view=view[view.apply(lambda r: query in f"{r['name']} {r['location']} {r['serial_number']} {r['registered_by']}".lower(),axis=1)]
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


def fmt_money(v):
    try:
        return f"{float(v):,.0f} ₮" if v not in (None, "") else "—"
    except (TypeError, ValueError):
        return "—"


def asset_detail(asset_id):
    """QR кодоор нээгдэх нэг төхөөрөмжийн дэлгэрэнгүй хуудас."""
    row = asset_by_id(asset_id)
    if not row:
        st.error("Ийм ID-тай бүртгэл олдсонгүй."); return
    esc = lambda v: html.escape(str(v or "—"))
    st.markdown(
        f'<div class="hero"><div class="hero-kicker">Бүртгэл #{row["id"]}</div>'
        f'<div class="hero-title">{esc(row["name"])}</div>'
        f'<p class="hero-subtitle">{esc(row["location"])} · {esc(row["status"])}</p></div>',
        unsafe_allow_html=True)
    left, right = st.columns([2, 1])
    with left:
        info = {
            "Серийн дугаар": row.get("serial_number"), "Тоо ширхэг": row.get("quantity"),
            "Худалдан авсан": row.get("purchase_date"), "Үнэ": fmt_money(row.get("purchase_price")),
            "Баталгаат хугацаа": row.get("warranty_until"), "Бүртгэсэн": row.get("registered_by"),
            "Бүртгэсэн огноо": row.get("created_at"), "Сүүлд шинэчилсэн": row.get("updated_at"),
            "Тайлбар": row.get("notes"),
        }
        for k, v in info.items():
            st.markdown(f"**{k}:** {v if v not in (None, '') else '—'}")
    with right:
        if row.get("image_url"):
            st.image(row["image_url"], use_container_width=True)
        st.image(qr_png(app_url(row)), width=160)
    with get_engine().connect() as conn:
        rep = pd.read_sql_query(select(repairs).where(repairs.c.asset_id == int(asset_id)).order_by(repairs.c.id.desc()), conn)
        tr = pd.read_sql_query(select(transfers).where(transfers.c.asset_id == int(asset_id)).order_by(transfers.c.id.desc()), conn)
    st.markdown("### Засварын түүх")
    if rep.empty: st.caption("Засварын түүх алга.")
    else: st.dataframe(rep, hide_index=True, use_container_width=True)
    st.markdown("### Шилжүүлгийн түүх")
    if tr.empty: st.caption("Шилжүүлгийн түүх алга.")
    else: st.dataframe(tr, hide_index=True, use_container_width=True)


role = require_login()
df = load_assets()

# Sidebar navigation — өгөгдлийн логик өөрчлөгдөөгүй, зөвхөн UI-ийн navigation.
with st.sidebar:
    show_logos(56)
    st.markdown('<div class="nav-title" style="margin-top:.6rem">ХААИС</div><div class="nav-caption">Тоног төхөөрөмжийн систем</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="nav-caption">ҮНДСЭН ЦЭС</div>', unsafe_allow_html=True)
    if role == "admin":
        pages = ["⌂  Dashboard", "＋  Бүртгэх", "▦  Тоног төхөөрөмж", "✎  Удирдах", "⚒  Засвар", "↔  Шилжүүлэг", "▣  QR төв", "⇩  Тайлан"]
    elif role in ["treasurer", "teacher"]:
        pages = ["⌂  Dashboard", "＋  Бүртгэх", "▦  Тоног төхөөрөмж", "⚒  Засвар", "↔  Шилжүүлэг", "▣  QR төв", "⇩  Тайлан"]
    else:
        pages = ["⌂  Dashboard", "▦  Тоног төхөөрөмж", "▣  QR төв"]
    page = st.radio("Цэс", pages, label_visibility="collapsed", key="main_nav", on_change=st.query_params.clear)
    st.markdown("---")
    st.caption(f"Нэвтэрсэн эрх: {role.upper()}")
    if st.button("⎋  Гарах", use_container_width=True):
        st.session_state.clear(); st.rerun()

# Top bar and brand header.
top_left, top_right = st.columns([6, 2])
with top_left:
    st.markdown('<div class="page-title">Тоног төхөөрөмжийн бүртгэл</div><div class="page-caption">ХААИС-ийн хөрөнгө удирдлагын нэгдсэн систем</div>', unsafe_allow_html=True)
with top_right:
    show_logos(44)

# QR кодоор (?id=5) орж ирсэн бол тухайн төхөөрөмжийн хуудсыг харуулна.
scan_id = st.query_params.get("id")
if scan_id:
    if st.button("← Жагсаалт руу буцах"):
        st.query_params.clear(); st.rerun()
    if str(scan_id).isdigit():
        asset_detail(int(scan_id))
    else:
        st.error("QR кодын холбоос буруу байна.")
    st.stop()

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
                if value:
                    qid = parse_qs(urlparse(value).query).get("id", [None])[0]
                    if qid and qid.isdigit():
                        st.query_params["id"] = qid; st.rerun()
                    st.warning(f"Энэ QR манай системийн бүртгэл биш байна: {value}")
                else: st.warning("QR код танигдсангүй. Камераа ойртуулж дахин оролдоно уу.")
            except ImportError: st.info("QR camera-д opencv-python-headless шаардлагатай.")
