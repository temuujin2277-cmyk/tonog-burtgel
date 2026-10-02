"""
Сургуулийн тоног төхөөрөмж бүртгэх апп (v3)
- Хоёр түвшний нууц үг:
    APP_PASSWORD    -> Админ (бүртгэх, засах, устгах)
    VIEWER_PASSWORD -> Үзэгч (зөвхөн жагсаалт харах, QR үүсгэх)
- Өгөгдөл: Postgres (Supabase) -> st.secrets["DATABASE_URL"]
  DATABASE_URL байхгүй бол локал assets.db (SQLite) ашиглана.
"""

import hmac
import io
from datetime import datetime

import pandas as pd
import qrcode
import streamlit as st
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, delete, insert, select, update

STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]

st.set_page_config(page_title="Хөрөнгө бүртгэл", page_icon="🏫", layout="wide")


# ---------- Secrets ----------
def secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


# ---------- Нууц үг ----------
def matches(pw, expected):
    return bool(expected) and hmac.compare_digest(pw.encode(), str(expected).encode())


def require_login() -> str:
    admin_pw = secret("APP_PASSWORD")
    viewer_pw = secret("VIEWER_PASSWORD")
    if not admin_pw:
        st.error("APP_PASSWORD тохируулаагүй байна. Secrets хэсэгт нэмнэ үү.")
        st.stop()

    role = st.session_state.get("role")
    if role:
        with st.sidebar:
            st.caption("Эрх: " + ("Админ" if role == "admin" else "Үзэгч"))
            if st.button("Гарах"):
                st.session_state["role"] = None
                st.rerun()
        return role

    st.title("🔒 Нэвтрэх")
    with st.form("login_form"):
        pw = st.text_input("Нууц үг", type="password")
        ok = st.form_submit_button("Нэвтрэх")
    if ok:
        if matches(pw, admin_pw):
            st.session_state["role"] = "admin"
            st.rerun()
        elif matches(pw, viewer_pw):
            st.session_state["role"] = "viewer"
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
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
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


def update_asset(asset_id, name, location, quantity, status):
    with get_engine().begin() as conn:
        conn.execute(
            update(assets)
            .where(assets.c.id == asset_id)
            .values(name=name, location=location, quantity=quantity, status=status)
        )


def delete_asset(asset_id):
    with get_engine().begin() as conn:
        conn.execute(delete(assets).where(assets.c.id == asset_id))


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


def asset_options(df):
    return {f"#{r['id']} — {r['name']} ({r['location']})": r for _, r in df.iterrows()}


# ---------- Табууд ----------
def render_add():
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


def render_list():
    df = load_assets()
    if df.empty:
        st.info("Одоогоор бүртгэгдсэн хөрөнгө алга.")
        return

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


def render_edit():
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    df = load_assets()
    if df.empty:
        st.info("Засах хөрөнгө алга.")
        return

    options = asset_options(df)
    choice = st.selectbox("Засах хөрөнгө сонгох", list(options.keys()), key="edit_choice")
    row = options[choice]
    rid = int(row["id"])

    with st.form(f"edit_form_{rid}"):
        e_name = st.text_input("Хөрөнгийн нэр", value=row["name"], key=f"e_name_{rid}")
        e_loc = st.text_input("Анги / байршил", value=row["location"], key=f"e_loc_{rid}")
        e_qty = st.number_input(
            "Тоо ширхэг", min_value=1, value=int(row["quantity"]), step=1, key=f"e_qty_{rid}"
        )
        idx = STATUSES.index(row["status"]) if row["status"] in STATUSES else 0
        e_status = st.selectbox("Төлөв", STATUSES, index=idx, key=f"e_status_{rid}")
        save = st.form_submit_button("💾 Хадгалах")

    if save:
        if not e_name.strip() or not e_loc.strip():
            st.error("Нэр болон байршлыг заавал бөглөнө үү.")
        else:
            update_asset(rid, e_name.strip(), e_loc.strip(), int(e_qty), e_status)
            st.session_state["flash"] = f"✅ #{rid} амжилттай шинэчлэгдлээ."
            st.rerun()

    st.divider()
    st.subheader("Устгах")
    confirm = st.checkbox("Энэ хөрөнгийг устгахыг зөвшөөрч байна", key=f"confirm_del_{rid}")
    if st.button("🗑️ Устгах", disabled=not confirm, key=f"del_{rid}"):
        delete_asset(rid)
        st.session_state["flash"] = f"🗑️ #{rid} устгагдлаа."
        st.rerun()


def render_qr():
    df = load_assets()
    if df.empty:
        st.info("QR код үүсгэхийн тулд эхлээд хөрөнгө бүртгэнэ үү.")
        return

    options = asset_options(df)
    choice = st.selectbox("Хөрөнгө сонгох", list(options.keys()), key="qr_choice")
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


# ---------- Үндсэн интерфейс ----------
role = require_login()

st.title("🏫 Сургуулийн тоног төхөөрөмжийн бүртгэл")

if role == "admin":
    tab_add, tab_list, tab_edit, tab_qr = st.tabs(
        ["➕ Шинээр бүртгэх", "📋 Жагсаалт", "✏️ Засах / устгах", "🔳 QR код"]
    )
    with tab_add:
        render_add()
    with tab_list:
        render_list()
    with tab_edit:
        render_edit()
    with tab_qr:
        render_qr()
else:
    tab_list, tab_qr = st.tabs(["📋 Жагсаалт", "🔳 QR код"])
    with tab_list:
        render_list()
    with tab_qr:
        render_qr()
