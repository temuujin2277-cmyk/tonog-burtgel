import io
import sqlite3
from datetime import datetime

import pandas as pd
import qrcode
import streamlit as st

DB_PATH = "assets.db"
STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]


# ---------- Өгөгдлийн сан ----------
def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                location   TEXT    NOT NULL,
                quantity   INTEGER NOT NULL CHECK (quantity > 0),
                status     TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
            """
        )


def add_asset(name, location, quantity, status):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO assets (name, location, quantity, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, location, quantity, status, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )


def load_assets() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT id, name, location, quantity, status, created_at "
            "FROM assets ORDER BY id DESC",
            conn,
        )


# ---------- QR код ----------
def make_qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(box_size=12, border=4, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def asset_payload(row) -> str:
    return f"ASSET-{row['id']}"

# ---------- Интерфейс ----------
st.set_page_config(page_title="Хөрөнгө бүртгэл", page_icon="🏫", layout="wide")
init_db()

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
            use_container_width=True,
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
            st.text(f"ID: {row['id']}\nНэр: {row['name']}\nБайршил: {row['location']}\nТоо: {row['quantity']}\nТөлөв: {row['status']}")
            st.download_button(
                "⬇️ QR кодыг татах (PNG)",
                data=png,
                file_name=f"asset_{row['id']}_qr.png",
                mime="image/png",
            )
