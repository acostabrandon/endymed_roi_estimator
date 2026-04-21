from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="EndyMed PRO MAX Practice Revenue Planner",
    page_icon="💜",
    layout="wide",
)

APP_TITLE = "EndyMed PRO MAX Practice Revenue Planner"
APP_SUBTITLE = "Internal sales planning tool for modeling treatment revenue across selected PRO MAX offerings."
DATA_PATH = Path(__file__).with_name("presets.csv")
MAX_ROWS = 20


@st.cache_data
def load_presets() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df = df[df["active_in_app"].astype(str).str.lower() == "yes"].copy()
    numeric_cols = [
        "sessions_default",
        "package_low",
        "package_high",
        "per_session_low",
        "per_session_high",
        "consumable_per_session",
        "display_order",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["pricing_mode_default"] = (
        df["pricing_mode_default"].fillna("package").astype(str).str.lower()
    )
    df["section"] = df["section"].fillna("").astype(str)
    df["preset_name"] = df["preset_name"].fillna("").astype(str)
    df["option_label"] = df["section"] + " — " + df["preset_name"]
    return df.sort_values(["section", "display_order", "preset_name"]).reset_index(drop=True)


def money(value: float) -> str:
    return f"${value:,.0f}"


def init_state(df: pd.DataFrame) -> None:
    if "row_count" not in st.session_state:
        st.session_state.row_count = 1
    if "preset_map" not in st.session_state:
        records = df.to_dict(orient="records")
        st.session_state.preset_map = {
            record["option_label"]: record for record in records
        }


def add_row() -> None:
    if st.session_state.row_count < MAX_ROWS:
        st.session_state.row_count += 1


def remove_row(row_idx: int) -> None:
    active_rows = st.session_state.get("active_rows", {})
    active_rows[row_idx] = False
    st.session_state.active_rows = active_rows


def ensure_row_initialized(row_idx: int, default_label: str, preset_map: dict) -> None:
    selected_key = f"row_{row_idx}_selected"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = default_label

    active_rows = st.session_state.get("active_rows", {})
    if row_idx not in active_rows:
        active_rows[row_idx] = True
        st.session_state.active_rows = active_rows

    record = preset_map[st.session_state[selected_key]]
    apply_defaults_from_record(row_idx, record, force_if_missing=True)
    last_preset_key = f"row_{row_idx}_last_preset"
    if last_preset_key not in st.session_state:
        st.session_state[last_preset_key] = st.session_state[selected_key]



def apply_defaults_from_record(row_idx: int, record: dict, force_if_missing: bool = False) -> None:
    defaults = {
        f"row_{row_idx}_pricing_mode": record["pricing_mode_default"] if record["pricing_mode_default"] in {"package", "per_session"} else "package",
        f"row_{row_idx}_sessions": int(record["sessions_default"]),
        f"row_{row_idx}_package_low": float(record["package_low"]),
        f"row_{row_idx}_package_high": float(record["package_high"]),
        f"row_{row_idx}_per_session_low": float(record["per_session_low"]),
        f"row_{row_idx}_per_session_high": float(record["per_session_high"]),
        f"row_{row_idx}_volume": 0,
    }
    for key, value in defaults.items():
        if force_if_missing:
            if key not in st.session_state:
                st.session_state[key] = value
        else:
            st.session_state[key] = value



def sync_row_on_preset_change(row_idx: int, preset_map: dict) -> dict:
    selected_key = f"row_{row_idx}_selected"
    current_label = st.session_state[selected_key]
    current_record = preset_map[current_label]
    last_preset_key = f"row_{row_idx}_last_preset"
    previous_label = st.session_state.get(last_preset_key)
    if current_label != previous_label:
        apply_defaults_from_record(row_idx, current_record, force_if_missing=False)
        st.session_state[last_preset_key] = current_label
    return current_record



def calculate_row(record: dict, pricing_mode: str, sessions: int, package_low: float, package_high: float,
                  per_session_low: float, per_session_high: float, volume: int) -> dict:
    consumable_per_session = float(record["consumable_per_session"])
    if pricing_mode == "per_session":
        monthly_gross_low = volume * per_session_low
        monthly_gross_high = volume * per_session_high
        monthly_consumable = volume * consumable_per_session
        volume_label = "Monthly Treatments Performed"
    else:
        monthly_gross_low = volume * package_low
        monthly_gross_high = volume * package_high
        monthly_consumable = volume * sessions * consumable_per_session
        volume_label = "Monthly New Patients Starting Program"

    monthly_adjusted_low = monthly_gross_low - monthly_consumable
    monthly_adjusted_high = monthly_gross_high - monthly_consumable

    return {
        "section": record["section"],
        "preset_name": record["preset_name"],
        "pricing_mode": pricing_mode,
        "sessions": sessions,
        "volume": volume,
        "volume_label": volume_label,
        "monthly_gross_low": monthly_gross_low,
        "monthly_gross_high": monthly_gross_high,
        "monthly_consumable": monthly_consumable,
        "monthly_adjusted_low": monthly_adjusted_low,
        "monthly_adjusted_high": monthly_adjusted_high,
        "annual_adjusted_low": monthly_adjusted_low * 12,
        "annual_adjusted_high": monthly_adjusted_high * 12,
        "consumable_per_session": consumable_per_session,
    }



def render_value_card(title: str, value: str, help_text: str | None = None) -> None:
    help_html = f"<div class='card-help'>{help_text}</div>" if help_text else ""
    st.markdown(
        f"""
        <div class="value-card">
            <div class="card-title">{title}</div>
            <div class="card-value">{value}</div>
            {help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_row(row_idx: int, option_labels: list[str], preset_map: dict) -> dict | None:
    if not st.session_state.get("active_rows", {}).get(row_idx, True):
        return None

    current_record = sync_row_on_preset_change(row_idx, preset_map)
    selected_label = st.session_state[f"row_{row_idx}_selected"]
    row_title = f"Treatment {row_idx + 1} — {selected_label}"

    with st.expander(row_title, expanded=(row_idx == 0)):
        top_cols = st.columns([6, 1.2])
        with top_cols[0]:
            st.selectbox(
                "Treatment",
                options=option_labels,
                key=f"row_{row_idx}_selected",
                help="All presets are listed together and grouped by pillar in the label.",
            )
        with top_cols[1]:
            st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
            if st.button("Remove", key=f"remove_{row_idx}"):
                remove_row(row_idx)
                st.rerun()

        current_record = sync_row_on_preset_change(row_idx, preset_map)

        mode_map = {"Package Pricing": "package", "Per Session Pricing": "per_session"}
        reverse_mode_map = {v: k for k, v in mode_map.items()}
        current_mode = st.session_state.get(f"row_{row_idx}_pricing_mode", "package")
        selected_mode_label = st.radio(
            "Pricing Mode",
            options=list(mode_map.keys()),
            horizontal=True,
            key=f"row_{row_idx}_pricing_mode_ui",
            index=list(mode_map.keys()).index(reverse_mode_map.get(current_mode, "Package Pricing")),
        )
        pricing_mode = mode_map[selected_mode_label]
        st.session_state[f"row_{row_idx}_pricing_mode"] = pricing_mode

        cols = st.columns([1, 1, 1])
        with cols[0]:
            sessions = st.number_input(
                "Sessions per Package",
                min_value=1,
                step=1,
                key=f"row_{row_idx}_sessions",
                disabled=(pricing_mode == "per_session"),
            )

        if pricing_mode == "package":
            with cols[1]:
                st.number_input(
                    "Package Low ($)",
                    min_value=0.0,
                    step=50.0,
                    key=f"row_{row_idx}_package_low",
                )
            with cols[2]:
                st.number_input(
                    "Package High ($)",
                    min_value=0.0,
                    step=50.0,
                    key=f"row_{row_idx}_package_high",
                )
        else:
            with cols[1]:
                st.number_input(
                    "Per-Session Low ($)",
                    min_value=0.0,
                    step=25.0,
                    key=f"row_{row_idx}_per_session_low",
                )
            with cols[2]:
                st.number_input(
                    "Per-Session High ($)",
                    min_value=0.0,
                    step=25.0,
                    key=f"row_{row_idx}_per_session_high",
                )

        volume_label = "Monthly Treatments Performed" if pricing_mode == "per_session" else "Monthly New Patients Starting Program"
        volume = st.number_input(volume_label, min_value=0, step=1, key=f"row_{row_idx}_volume")

        calc = calculate_row(
            record=current_record,
            pricing_mode=pricing_mode,
            sessions=int(st.session_state[f"row_{row_idx}_sessions"]),
            package_low=float(st.session_state[f"row_{row_idx}_package_low"]),
            package_high=float(st.session_state[f"row_{row_idx}_package_high"]),
            per_session_low=float(st.session_state[f"row_{row_idx}_per_session_low"]),
            per_session_high=float(st.session_state[f"row_{row_idx}_per_session_high"]),
            volume=int(volume),
        )

        metric_cols = st.columns(3)
        with metric_cols[0]:
            render_value_card(
                "Monthly Gross Revenue",
                f"{money(calc['monthly_gross_low'])} – {money(calc['monthly_gross_high'])}",
            )
        with metric_cols[1]:
            render_value_card(
                "Monthly Direct Consumable Cost",
                money(calc["monthly_consumable"]),
            )
        with metric_cols[2]:
            render_value_card(
                "Monthly Adjusted Revenue",
                f"{money(calc['monthly_adjusted_low'])} – {money(calc['monthly_adjusted_high'])}",
                help_text=f"Annual adjusted: {money(calc['annual_adjusted_low'])} – {money(calc['annual_adjusted_high'])}",
            )

        if float(current_record["consumable_per_session"]) > 0:
            st.caption(
                f"Behind-the-scenes consumable assumption: {money(float(current_record['consumable_per_session']))} per applicable treatment session."
            )
        else:
            st.caption("Behind-the-scenes consumable assumption: no direct consumable cost applied.")

    return calc



def inject_css() -> None:
    st.markdown(
        """
        <style>
        .value-card {
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 16px;
            padding: 16px 18px;
            background: rgba(255,255,255,0.02);
            min-height: 112px;
        }
        .card-title {
            font-size: 0.92rem;
            color: rgba(255,255,255,0.72);
            margin-bottom: 12px;
        }
        .card-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.2;
        }
        .card-help {
            margin-top: 10px;
            color: rgba(255,255,255,0.68);
            font-size: 0.88rem;
        }
        .summary-card {
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 18px;
            padding: 18px 20px;
            background: rgba(255,255,255,0.03);
            min-height: 126px;
        }
        .summary-title {
            font-size: 0.9rem;
            color: rgba(255,255,255,0.7);
            margin-bottom: 10px;
        }
        .summary-value {
            font-size: 1.75rem;
            line-height: 1.15;
            font-weight: 800;
            color: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def render_summary_card(title: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-title">{title}</div>
            <div class="summary-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def main() -> None:
    df = load_presets()
    preset_map = {row["option_label"]: row.to_dict() for _, row in df.iterrows()}
    option_labels = df["option_label"].tolist()
    default_label = option_labels[0]

    init_state(df)
    inject_css()

    st.title(APP_TITLE)
    st.markdown(APP_SUBTITLE)
    st.info(
        "Select treatments one row at a time. Each preset auto-loads the suggested sessions and pricing ranges. "
        "This tool is for internal planning only and is not a guarantee of profitability."
    )

    header_cols = st.columns([2, 1])
    with header_cols[0]:
        st.subheader("Treatments")
        st.caption("Each dropdown includes all presets. The treatment pillar is shown in the label.")
    with header_cols[1]:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("+ Add Another Treatment", on_click=add_row, use_container_width=True)

    all_results: list[dict] = []
    for row_idx in range(st.session_state.row_count):
        ensure_row_initialized(row_idx, default_label, preset_map)
        result = render_row(row_idx, option_labels, preset_map)
        if result:
            all_results.append(result)

    gross_low = sum(r["monthly_gross_low"] for r in all_results)
    gross_high = sum(r["monthly_gross_high"] for r in all_results)
    total_consumable = sum(r["monthly_consumable"] for r in all_results)
    adjusted_low = sum(r["monthly_adjusted_low"] for r in all_results)
    adjusted_high = sum(r["monthly_adjusted_high"] for r in all_results)
    annual_low = sum(r["annual_adjusted_low"] for r in all_results)
    annual_high = sum(r["annual_adjusted_high"] for r in all_results)

    st.divider()
    st.subheader("Total Practice Revenue Summary")
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_summary_card("Total Monthly Gross Revenue", f"{money(gross_low)} – {money(gross_high)}")
    with summary_cols[1]:
        render_summary_card("Total Monthly Direct Consumable Cost", money(total_consumable))
    with summary_cols[2]:
        render_summary_card("Total Monthly Adjusted Revenue", f"{money(adjusted_low)} – {money(adjusted_high)}")
    with summary_cols[3]:
        render_summary_card("Annualized Adjusted Revenue", f"{money(annual_low)} – {money(annual_high)}")

    with st.expander("Optional Finance Input"):
        finance_payment = st.number_input("Monthly Finance Payment ($)", min_value=0.0, step=50.0, value=0.0)
        post_finance_low = adjusted_low - finance_payment
        post_finance_high = adjusted_high - finance_payment
        finance_cols = st.columns(2)
        with finance_cols[0]:
            render_summary_card("Monthly Finance Payment", money(finance_payment))
        with finance_cols[1]:
            render_summary_card("Post-Finance Monthly Adjusted Revenue", f"{money(post_finance_low)} – {money(post_finance_high)}")

    st.caption(
        "Internal planning estimate only. Excludes taxes, provider compensation, overhead, marketing allocation, labor allocation, and other operating costs unless manually entered elsewhere."
    )


if __name__ == "__main__":
    main()
