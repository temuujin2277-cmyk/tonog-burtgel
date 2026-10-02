"""
Сургуулийн тоног төхөөрөмж бүртгэх апп (v4)
- Хоёр түвшний нууц үг:
    APP_PASSWORD    -> Админ (бүртгэх, засах, устгах, жагсаалт, QR)
    VIEWER_PASSWORD -> Багш (бүртгэх, жагсаалт харах, QR үүсгэх; засах/устгах эрхгүй)
- "Бүртгэсэн багшийн нэр" талбар (registered_by)
- Өгөгдөл: Postgres (Supabase) -> st.secrets["DATABASE_URL"]
  DATABASE_URL байхгүй бол локал assets.db (SQLite) ашиглана.
"""

import hmac
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import qrcode
import streamlit as st
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, delete, insert, inspect, select, text, update

STATUSES = ["Хэвийн", "Засвартай", "Эвдэрсэн", "Актласан"]

st.set_page_config(page_title="Тоног төхөөрөмжийн бүртгэл", page_icon="🏫", layout="wide", initial_sidebar_state="expanded")

LOGO_PATH = Path(__file__).parent / "assets" / "HAAIS.png"

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 10% 0%,#20233a 0,#0d0f16 42%,#0b0c11 100%)}
[data-testid="stHeader"]{background:transparent}[data-testid="stSidebar"]{background:rgba(18,20,30,.92);border-right:1px solid rgba(139,92,246,.18)}
.block-container{max-width:1220px;padding-top:2.5rem;padding-bottom:4rem} h1{letter-spacing:-.035em;font-weight:800!important}
[data-testid="stForm"]{background:rgba(23,25,35,.82);border:1px solid rgba(148,163,184,.16);border-radius:16px;padding:1.35rem}
.hero{padding:1.4rem 1.55rem;border:1px solid rgba(139,92,246,.26);border-radius:20px;background:linear-gradient(120deg,rgba(124,58,237,.22),rgba(6,182,212,.08));margin-bottom:1.25rem}
.hero-kicker{color:#a78bfa;text-transform:uppercase;letter-spacing:.14em;font-size:.72rem;font-weight:700}.hero-title{font-size:2.2rem;line-height:1.1;font-weight:800;margin:.35rem 0}.hero-subtitle{color:#aeb5c7;margin:0}
.metric{background:linear-gradient(145deg,rgba(31,34,48,.96),rgba(20,22,31,.92));border:1px solid rgba(148,163,184,.14);border-radius:16px;padding:1rem 1.1rem;min-height:104px}.metric-label{color:#9ca3b8;font-size:.78rem;text-transform:uppercase;letter-spacing:.07em}.metric-value{color:#f8fafc;font-size:1.75rem;font-weight:800;margin-top:.4rem}.metric-note{color:#8b5cf6;font-size:.78rem;margin-top:.1rem}.section-label{color:#aeb5c7;font-size:.82rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;margin:1.1rem 0 .55rem}
button[kind="primary"]{background:linear-gradient(135deg,#8b5cf6,#6366f1)!important;border:0!important}[data-testid="stDataFrame"]{border-radius:14px;overflow:hidden;border:1px solid rgba(148,163,184,.14)}.stTabs [data-baseweb="tab-list"]{gap:8px;border-bottom:1px solid rgba(148,163,184,.14)}.stTabs [data-baseweb="tab"]{padding:.7rem 1rem}@media(max-width:700px){.hero-title{font-size:1.65rem}.block-container{padding:1rem}}
</style>
""", unsafe_allow_html=True)


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
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=90)
            st.markdown("**ХААИС**  \nТоног төхөөрөмжийн систем")
            st.caption("Эрх: " + ("Админ" if role == "admin" else "Багш"))
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
    Column("registered_by", String(100), nullable=True),
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
    # Хуучин хүснэгтэд registered_by багана байхгүй бол автоматаар нэмнэ
    columns = [c["name"] for c in inspect(engine).get_columns("assets")]
    if "registered_by" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE assets ADD COLUMN registered_by VARCHAR(100)"))
    return engine


def add_asset(name, location, quantity, status, registered_by):
    with get_engine().begin() as conn:
        conn.execute(
            insert(assets).values(
                name=name,
                location=location,
                quantity=quantity,
                status=status,
                registered_by=registered_by,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
        )


def update_asset(asset_id, name, location, quantity, status, registered_by):
    with get_engine().begin() as conn:
        conn.execute(
            update(assets)
            .where(assets.c.id == asset_id)
            .values(
                name=name,
                location=location,
                quantity=quantity,
                status=status,
                registered_by=registered_by,
            )
        )


def delete_asset(asset_id):
    with get_engine().begin() as conn:
        conn.execute(delete(assets).where(assets.c.id == asset_id))


def load_assets() -> pd.DataFrame:
    with get_engine().connect() as conn:
        df = pd.read_sql_query(select(assets).order_by(assets.c.id.desc()), conn)
    df["registered_by"] = df["registered_by"].fillna("")
    return df


def get_asset(asset_id):
    with get_engine().connect() as conn:
        r = conn.execute(select(assets).where(assets.c.id == asset_id)).mappings().first()
    return dict(r) if r else None


# ---------- QR код ----------
def make_qr_png(text_value: str) -> bytes:
    qr = qrcode.QRCode(
        box_size=12,
        border=4,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
    )
    qr.add_data(text_value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


APP_URL_DEFAULT = "https://tonog-burtgel-9kpnaomprgjcdxjgbkhvc5.streamlit.app"


def asset_payload(row) -> str:
    base = str(secret("APP_URL", APP_URL_DEFAULT)).rstrip("/")
    return f"{base}/?id={row['id']}"


def asset_options(df):
    return {f"#{r['id']} — {r['name']} ({r['location']})": r for _, r in df.iterrows()}


# ---------- QR-аар нээгдсэн хөрөнгийн карт ----------
def render_scanned_asset():
    raw = st.query_params.get("id")
    if not raw:
        return
    try:
        asset_id = int(raw)
    except (TypeError, ValueError):
        st.warning("QR кодын дугаар буруу байна.")
        return

    row = get_asset(asset_id)
    with st.container(border=True):
        if row is None:
            st.warning(f"#{asset_id} дугаартай хөрөнгө олдсонгүй.")
        else:
            st.subheader(f"🔎 {row['name']}")
            c1, c2 = st.columns(2)
            c1.markdown(
                f"**ID:** {row['id']}  \n"
                f"**Анги / байршил:** {row['location']}  \n"
                f"**Тоо ширхэг:** {row['quantity']}"
            )
            c2.markdown(
                f"**Төлөв:** {row['status']}  \n"
                f"**Бүртгэсэн багш:** {row['registered_by'] or '—'}  \n"
                f"**Бүртгэсэн огноо:** {row['created_at']}"
            )
        if st.button("✖ Хаах", key="close_scan"):
            st.query_params.clear()
            st.rerun()


# ---------- Табууд ----------
def render_add():
    registrant = st.text_input(
        "Бүртгэсэн багшийн нэр", key="registrant", placeholder="Жишээ: Б. Болд"
    )
    st.markdown('<div class="section-label">Шинэ хөрөнгө оруулах</div>', unsafe_allow_html=True)
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Хөрөнгийн нэр", placeholder="Жишээ: Проектор")
        with c2:
            location = st.text_input("Анги / байршил", placeholder="Жишээ: 12а анги, 204 тоот")
        c3, c4 = st.columns(2)
        with c3:
            quantity = st.number_input("Тоо ширхэг", min_value=1, value=1, step=1)
        with c4:
            status = st.selectbox("Төлөв", STATUSES)
        submitted = st.form_submit_button("＋  Бүртгэх", type="primary", use_container_width=True)

    if submitted:
        if not registrant.strip():
            st.error("Дээд талын «Бүртгэсэн багшийн нэр» талбарыг бөглөнө үү.")
        elif not name.strip() or not location.strip():
            st.error("Нэр болон байршлыг заавал бөглөнө үү.")
        else:
            add_asset(name.strip(), location.strip(), int(quantity), status, registrant.strip())
            st.success(f"✅ «{name.strip()}» амжилттай бүртгэгдлээ.")


def render_list():
    df = load_assets()
    if df.empty:
        st.info("Одоогоор бүртгэгдсэн хөрөнгө алга.")
        return

    c1, c2 = st.columns(2)
    search = c1.text_input("🔍 Нэр / байршил / багшаар хайх")
    status_filter = c2.multiselect("Төлвөөр шүүх", STATUSES)

    view = df
    if search:
        mask = (
            view["name"].str.contains(search, case=False, na=False)
            | view["location"].str.contains(search, case=False, na=False)
            | view["registered_by"].str.contains(search, case=False, na=False)
        )
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
                "registered_by": "Бүртгэсэн багш",
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
        e_by = st.text_input(
            "Бүртгэсэн багшийн нэр", value=row["registered_by"], key=f"e_by_{rid}"
        )
        save = st.form_submit_button("💾 Хадгалах")

    if save:
        if not e_name.strip() or not e_loc.strip():
            st.error("Нэр болон байршлыг заавал бөглөнө үү.")
        else:
            update_asset(rid, e_name.strip(), e_loc.strip(), int(e_qty), e_status, e_by.strip())
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
            f"Бүртгэсэн: {row['registered_by'] or '—'}\n"
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

hero_logo, hero_text = st.columns([1, 9], vertical_alignment="center")
with hero_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=92)
with hero_text:
    st.markdown("""
    <div class="hero"><div class="hero-kicker">ХААИС · School asset management</div><div class="hero-title">Тоног төхөөрөмжийн бүртгэл</div><p class="hero-subtitle">Сургуулийн хөрөнгийг нэг дороос бүртгэж, хянаж, QR кодоор таних систем</p></div>
    """, unsafe_allow_html=True)

overview_df = load_assets()
total_items = int(overview_df["quantity"].sum()) if not overview_df.empty else 0
healthy = int((overview_df["status"] == "Хэвийн").sum()) if not overview_df.empty else 0
needs_attention = int(overview_df["status"].isin(["Засвартай", "Эвдэрсэн"]).sum()) if not overview_df.empty else 0
m1, m2, m3, m4 = st.columns(4)
with m1: st.markdown(f'<div class="metric"><div class="metric-label">Нийт төрөл</div><div class="metric-value">{len(overview_df)}</div><div class="metric-note">бүртгэл</div></div>', unsafe_allow_html=True)
with m2: st.markdown(f'<div class="metric"><div class="metric-label">Нийт тоо ширхэг</div><div class="metric-value">{total_items}</div><div class="metric-note">тоног төхөөрөмж</div></div>', unsafe_allow_html=True)
with m3: st.markdown(f'<div class="metric"><div class="metric-label">Хэвийн төлөв</div><div class="metric-value">{healthy}</div><div class="metric-note">төрөл</div></div>', unsafe_allow_html=True)
with m4: st.markdown(f'<div class="metric"><div class="metric-label">Анхаарах шаардлагатай</div><div class="metric-value">{needs_attention}</div><div class="metric-note">засвар / эвдрэл</div></div>', unsafe_allow_html=True)
st.write("")

render_scanned_asset()

if role == "admin":
    tab_add, tab_list, tab_edit, tab_qr = st.tabs(
        ["➕  Бүртгэх", "📋  Жагсаалт", "✏️  Удирдах", "🔳  QR код"]
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
    tab_add, tab_list, tab_qr = st.tabs(["➕  Бүртгэх", "📋  Жагсаалт", "🔳  QR код"])
    with tab_add:
        render_add()
    with tab_list:
        render_list()
    with tab_qr:
        render_qr()
