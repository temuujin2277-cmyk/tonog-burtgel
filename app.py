"""
Сургуулийн тоног төхөөрөмж бүртгэх апп (v2)
- Нууц үгээр нэвтрэх (st.secrets["APP_PASSWORD"])
- Өгөгдөл устахгүй: Postgres (Supabase) -> st.secrets["DATABASE_URL"]
  DATABASE_URL байхгүй бол локал assets.db (SQLite) ашиглана.
"""

import hmac
import io
from datetime import datetime

import pandas as pd
import qrcode
import streamlit as st
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert, select

STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]

st.set_page_config(page_title="Хөрөнгө бүртгэл", page_icon="🏫", layout="wide")


# ---------- Secrets ----------
def secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


# ---------- Нууц үг ----------
def require_login():
    expected = secret("APP_PASSWORD")
    if not expected:
        st.error("APP_PASSWORD тохируулаагүй байна. Secrets хэсэгт нэмнэ үү.")
        st.stop()

    if st.session_state.get("authed"):
        with st.sidebar:
            if st.button("Гарах"):
                st.session_state["authed"] = False
                st.rerun()
        return

    st.title("🔒 Нэвтрэх")
    with st.form("login_form"):
        pw = st.text_input("Нууц үг", type="password")
        ok = st.form_submit_button("Нэвтрэх")
    if ok:
        if hmac.compare_digest(pw.encode(), str(expected).encode()):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Нууц үг буруу байна.")
    st.stop()


# ---------- Өгөгдлийн сан ----------
metadata = MetaData()
assets = Table(
    "assets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), nullable=False),
    Column("location", String(200), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", String(50), nullable=False),
    Column("created_at", String(30), nullable=False),
)


@st.cache_resource
def get_engine():
    url = secret("DATABASE_URL", "sqlite:///assets.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)  # хүснэгт байхгүй бол үүсгэнэ
    return engine


def add_asset(name, location, quantity, status):
    with get_engine().begin() as conn:
        conn.execute(
            insert(assets).values(
                name=name,
                location=location,
                quantity=quantity,
                status=status,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
        )


def load_assets() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(select(assets).order_by(assets.c.id.desc()), conn)


# ---------- QR код ----------
def make_qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(
        box_size=12,
        border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def asset_payload(row) -> str:
    return f"ASSET-{row['id']}"


# ---------- Интерфейс ----------
require_login()

st.title("🏫 Сургуулийн тоног төхөөрөмжийн бүртгэл")

tab_add, tab_list, tab_qr = st.tabs(["➕ Шинээр бүртгэх", "📋 Жагсаалт", "🔳 QR код"])

# 1. Бүртгэх форм
with tab_add:
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Хөрөнгийн нэр", placeholder="Жишээ: Проектор")
        location = st.text_input("Анги / байршил", placeholder="Жишээ: 12а анги, 204 тоот")
        quantity = st.number_input("Тоо ширхэг", min_value=1, value=1, step=1)
        status = st.selectbox("Төлөв", STATUSES)
        submitted = st.form_submit_button("Бүртгэх")

    if submitted:
        if not name.strip() or not location.strip():
            st.error("Нэр болон байршлыг заавал бөглөнө үү.")
        else:
            add_asset(name.strip(), location.strip(), int(quantity), status)
            st.success(f"✅ «{name.strip()}» амжилттай бүртгэгдлээ.")

# 2. Хүснэгт
with tab_list:
    df = load_assets()
    if df.empty:
        st.info("Одоогоор бүртгэгдсэн хөрөнгө алга.")
    else:
        c1, c2 = st.columns(2)
        search = c1.text_input("🔍 Нэр / байршлаар хайх")
        status_filter = c2.multiselect("Төлвөөр шүүх", STATUSES)

        view = df
        if search:
            mask = view["name"].str.contains(search, case=False, na=False) | view[
                "location"
            ].str.contains(search, case=False, na=False)
            view = view[mask]
        if status_filter:
            view = view[view["status"].isin(status_filter)]

        st.dataframe(
            view.rename(
                columns={
                    "id": "ID",
                    "name": "Нэр",
                    "location": "Анги / байршил",
                    "quantity": "Тоо",
                    "status": "Төлөв",
                    "created_at": "Бүртгэсэн огноо",
                }
            ),
            hide_index=True,
        )
        st.caption(f"Нийт {len(view)} бичлэг")

# 3. QR код
with tab_qr:
    df = load_assets()
    if df.empty:
        st.info("QR код үүсгэхийн тулд эхлээд хөрөнгө бүртгэнэ үү.")
    else:
        options = {
            f"#{r['id']} — {r['name']} ({r['location']})": r for _, r in df.iterrows()
        }
        choice = st.selectbox("Хөрөнгө сонгох", list(options.keys()))
        row = options[choice]

        payload = asset_payload(row)
        png = make_qr_png(payload)

        col_img, col_info = st.columns([1, 2])
        with col_img:
            st.image(png, width=400)
        with col_info:
            st.text(
                f"ID: {row['id']}\n"
                f"Нэр: {row['name']}\n"
                f"Байршил: {row['location']}\n"
                f"Тоо: {row['quantity']}\n"
                f"Төлөв: {row['status']}\n"
                f"QR утга: {payload}"
            )
            st.download_button(
                "⬇️ QR кодыг татах (PNG)",
                data=png,
                file_name=f"asset_{row['id']}_qr.png",
                mime="image/png",
            )
