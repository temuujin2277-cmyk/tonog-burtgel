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
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 10% 0%,#20233a 0,#0d0f16 42%,#0b0c11 100%)}
[data-testid="stHeader"]{background:transparent}[data-testid="stSidebar"]{background:rgba(18,20,30,.94);border-right:1px solid rgba(139,92,246,.2)}
.block-container{max-width:1280px;padding-top:1.8rem;padding-bottom:4rem}.hero{padding:1.35rem 1.5rem;border:1px solid rgba(139,92,246,.3);border-radius:20px;background:linear-gradient(120deg,rgba(124,58,237,.22),rgba(6,182,212,.08));margin-bottom:1.2rem}
.hero-kicker,.section-label{color:#a78bfa;text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:700}.hero-title{font-size:2.15rem;font-weight:800;margin:.3rem 0}.hero-subtitle{color:#aeb5c7;margin:0}.metric{background:linear-gradient(145deg,rgba(31,34,48,.96),rgba(20,22,31,.92));border:1px solid rgba(148,163,184,.14);border-radius:16px;padding:1rem;min-height:100px}.metric-label{color:#9ca3b8;font-size:.75rem;text-transform:uppercase}.metric-value{color:#f8fafc;font-size:1.7rem;font-weight:800;margin-top:.35rem}.metric-note{color:#8b5cf6;font-size:.76rem}[data-testid="stForm"]{background:rgba(23,25,35,.82);border:1px solid rgba(148,163,184,.16);border-radius:16px;padding:1.15rem}.stTabs [data-baseweb="tab-list"]{gap:8px;border-bottom:1px solid rgba(148,163,184,.14)}button[kind="primary"]{background:linear-gradient(135deg,#8b5cf6,#6366f1)!important;border:0!important}@media(max-width:700px){.hero-title{font-size:1.6rem}.block-container{padding:1rem}}
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


role=require_login(); header(role); df=load_assets()
hero_logo,hero_text=st.columns([1,9],vertical_alignment="center")
with hero_logo:
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH),width=88)
with hero_text: st.markdown("<div class='hero'><div class='hero-kicker'>ХААИС · SCHOOL ASSET MANAGEMENT</div><div class='hero-title'>Тоног төхөөрөмжийн бүртгэл</div><p class='hero-subtitle'>Бүртгэл, тайлан, QR код, засвар ба шилжүүлгийн нэгдсэн систем</p></div>",unsafe_allow_html=True)
overview(df)

if role == "admin": tabs=st.tabs(["➕ Бүртгэх","📋 Жагсаалт","✏️ Удирдах","🛠 Засвар","↔ Шилжүүлэг","📊 Dashboard","⬇ Тайлан","🔳 QR"])
elif role in ["treasurer","teacher"]: tabs=st.tabs(["➕ Бүртгэх","📋 Жагсаалт","🛠 Засвар","↔ Шилжүүлэг","📊 Dashboard","⬇ Тайлан","🔳 QR"])
else: tabs=st.tabs(["📋 Жагсаалт","📊 Dashboard","🔳 QR"])

idx=0
if role in ["admin","treasurer","teacher"]:
    with tabs[idx]: add_form(role)
    idx+=1
with tabs[idx]: list_view(df)
idx+=1
if role=="admin":
    with tabs[idx]: edit_view(df,role)
    idx+=1
if role in ["admin","treasurer","teacher"]:
    with tabs[idx]: repairs_view(df,role)
    idx+=1
    with tabs[idx]: transfer_view(df,role)
    idx+=1
with tabs[idx]: charts_view(df)
idx+=1
if role in ["admin","treasurer","teacher"]:
    with tabs[idx]: reports_view(df)
    idx+=1
with tabs[idx]:
    if df.empty: st.info("QR үүсгэхийн тулд эхлээд бүртгэл нэмнэ үү.")
    else:
        opts={f"#{r.id} — {r['name']} ({r['location']})":r for _,r in df.iterrows()}; choice=st.selectbox("Төхөөрөмж",list(opts),key="qr_asset"); row=opts[choice]; payload=app_url(row); png=qr_png(payload)
        a,b=st.columns([1,2]); a.image(png,width=270); b.markdown(f"**{row['name']}**  \nID: #{row['id']}  \nБайршил: {row['location']}  \nТөлөв: {row['status']}"); b.download_button("⬇ QR татах",png,f"asset_{row['id']}_qr.png","image/png")
        st.markdown("**Утсаар QR уншуулах**")
        camera=st.camera_input("Камер нээх",key="qr_camera")
        if camera:
            try:
                import cv2, numpy as np
                value,_,_=cv2.QRCodeDetector().detectAndDecode(cv2.imdecode(np.frombuffer(camera.getvalue(),np.uint8),cv2.IMREAD_COLOR))
                if value: st.success(f"QR холбоос: {value}")
                else: st.warning("QR код танигдсангүй. Камераа ойртуулж дахин оролдоно уу.")
            except ImportError: st.info("Camera QR уншигчийг ажиллуулахын тулд opencv-python-headless нэмнэ үү.")
