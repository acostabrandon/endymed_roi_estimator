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
MAX_ROWS = 30


@st.cache_data
def load_presets() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df = df[df["active_in_app"].astype(str).str.strip().str.lower() == "yes"].copy()

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
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["pricing_mode_default"] = (
        df["pricing_mode_default"].fillna("package").astype(str).str.strip().str.lower()
    )
    df["section"] = df["section"].fillna("").astype(str).str.strip()
    df["preset_name"] = df["preset_name"].fillna("").astype(str).str.strip()

    df["option_label"] = df["section"] + " — " + df["preset_name"]

    df = df.sort_values(
        by=["section", "display_order", "preset_name"],
        ascending=[True, True, True],
    ).reset_index(drop=True)

    return df


def money(value: float) -> str:
    return f"${value:,.0f}"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        .top-note {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(60, 120, 255, 0.10);
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 24px;
            color: #d9e6ff;
            font-size: 1.02rem;
            line-height: 1.45;
        }

        .value-card {
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 16px;
            padding: 18px 18px 16px 18px;
            background: rgba(255,255,255,0.02);
            min-height: 118px;
        }

        .card-title {
            font-size: 0.92rem;
            color: rgba(255,255,255,0.72);
            margin-bottom: 12px;
        }

        .card-value {
            font-size: 1.7rem;
            font-weight: 750;
            line-height: 1.2;
            color: #ffffff;
            letter-spacing: -0.01em;
        }

        .card-help {
            margin-top: 10px;
            color: rgba(255,255,255,0.68);
            font-size: 0.88rem;
            line-height: 1.35;
        }

        .summary-card {
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 18px;
            padding: 18px 20px;
            background: rgba(255,255,255,0.03);
            min-height: 124px;
        }

        .summary-title {
            font-size: 0.9rem;
            color: rgba(255,255,255,0.7);
            margin-bottom: 10px;
        }

        .summary-value {
            font-size: 1.8rem;
            line-height: 1.15;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.01em;
        }

        div[data-testid="stExpander"] {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 14px;
        }

        div[data-testid="stExpander"] details summary {
            padding-top: 4px;
            padding-bottom: 4px;
        }

        .small-muted {
            color: rgba(255,255,255,0.68);
            font-size: 0.92rem;
        }

        .section-gap {
            height: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def init_state(df: pd.DataFrame) -> None:
    if "preset_map" not in st.session_state:
        records = df.to_dict(orient="records")
        st.session_state.preset_map = {
            record["option_label"]: record for record in records
        }

    if "option_labels" not in st.session_state:
        st.session_state.option_labels = df["option_label"].tolist()

    if "row_ids" not in st.session_state:
        st.session_state.row_ids = [0]

    if "next_row_id" not in st.session_state:
        st.session_state.next_row_id = 1

    default_label = st.session_state.option_labels[0]
    for row_id in st.session_state.row_ids:
        ensure_row_exists(row_id, default_label)


def ensure_row_exists(row_id: int, default_label: str) -> None:
    selected_key = f"row_{row_id}_selected"
    if selected_key not in st.session_state:
        st.session_state[selected_key] = default_label

    if f"row_{row_id}_pricing_mode" not in st.session_state:
        record = st.session_state.preset_map[st.session_state[selected_key]]
        default_mode = record.get("pricing_mode_default", "package")
        if default_mode not in {"package", "per_session"}:
            default_mode = "package"
        st.session_state[f"row_{row_id}_pricing_mode"] = default_mode

    if f"row_{row_id}_volume" not in st.session_state:
        st.session_state[f"row_{row_id}_volume"] = 0

    refresh_row_from_selected_preset(row_id, preserve_pricing_mode=True, force_if_missing=True)


def refresh_row_from_selected_preset(
    row_id: int,
    preserve_pricing_mode: bool = True,
    force_if_missing: bool = False,
) -> None:
    selected_label = st.session_state[f"row_{row_id}_selected"]
    record = st.session_state.preset_map[selected_label]

    if not preserve_pricing_mode:
        mode = record.get("pricing_mode_default", "package")
        if mode not in {"package", "per_session"}:
            mode = "package"
        st.session_state[f"row_{row_id}_pricing_mode"] = mode

    field_defaults = {
        f"row_{row_id}_sessions": max(int(record.get("sessions_default", 1)), 1),
        f"row_{row_id}_package_low": float(record.get("package_low", 0)),
        f"row_{row_id}_package_high": float(record.get("package_high", 0)),
        f"row_{row_id}_per_session_low": float(record.get("per_session_low", 0)),
        f"row_{row_id}_per_session_high": float(record.get("per_session_high", 0)),
    }

    for key, value in field_defaults.items():
        if force_if_missing:
            if key not in st.session_state:
                st.session_state[key] = value
        else:
            st.session_state[key] = value


def on_treatment_change(row_id: int) -> None:
    refresh_row_from_selected_preset(
        row_id=row_id,
        preserve_pricing_mode=True,
        force_if_missing=False,
    )


def add_row() -> None:
    if len(st.session_state.row_ids) >= MAX_ROWS:
        return

    row_id = st.session_state.next_row_id
    st.session_state.next_row_id += 1
    st.session_state.row_ids.append(row_id)

    default_label = st.session_state.option_labels[0]
    ensure_row_exists(row_id, default_label)


def remove_row(row_id: int) -> None:
    if len(st.session_state.row_ids) <= 1:
        return

    st.session_state.row_ids = [rid for rid in st.session_state.row_ids if rid != row_id]
    st.rerun()


def calculate_row(
    record: dict,
    pricing_mode: str,
    sessions: int,
    package_low: float,
    package_high: float,
    per_session_low: float,
    per_session_high: float,
    volume: int,
) -> dict:
    consumable_per_session = float(record.get("consumable_per_session", 0))

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
        "section": record.get("section", ""),
        "preset_name": record.get("preset_name", ""),
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


def render_row(row_id: int) -> dict | None:
    option_labels = st.session_state.option_labels
    preset_map = st.session_state.preset_map
    selected_label = st.session_state[f"row_{row_id}_selected"]
    record = preset_map[selected_label]

    row_title = f"Treatment {st.session_state.row_ids.index(row_id) + 1} — {selected_label}"

    with st.expander(row_title, expanded=(row_id == st.session_state.row_ids[0])):
        control_cols = st.columns([1.2, 3.8, 0.8])

        with control_cols[0]:
            st.radio(
                "Pricing Mode",
                options=["package", "per_session"],
                key=f"row_{row_id}_pricing_mode",
                horizontal=True,
                format_func=lambda x: "Package Pricing" if x == "package" else "Per Session Pricing",
            )

        with control_cols[1]:
            st.selectbox(
                "Treatment",
                options=option_labels,
                key=f"row_{row_id}_selected",
                on_change=on_treatment_change,
                args=(row_id,),
                help="All presets are included in one list. The label shows the treatment pillar.",
            )

        with control_cols[2]:
            st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
            st.button("Remove", key=f"remove_{row_id}", on_click=remove_row, args=(row_id,))

        pricing_mode = st.session_state[f"row_{row_id}_pricing_mode"]

        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)

        input_cols = st.columns([1, 1, 1])

        with input_cols[0]:
            st.number_input(
                "Sessions per Package",
                min_value=1,
                step=1,
                key=f"row_{row_id}_sessions",
                disabled=(pricing_mode == "per_session"),
            )

        if pricing_mode == "package":
            with input_cols[1]:
                st.number_input(
                    "Package Low ($)",
                    min_value=0.0,
                    step=50.0,
                    key=f"row_{row_id}_package_low",
                )
            with input_cols[2]:
                st.number_input(
                    "Package High ($)",
                    min_value=0.0,
                    step=50.0,
                    key=f"row_{row_id}_package_high",
                )
        else:
            with input_cols[1]:
                st.number_input(
                    "Per-Session Low ($)",
                    min_value=0.0,
                    step=25.0,
                    key=f"row_{row_id}_per_session_low",
                )
            with input_cols[2]:
                st.number_input(
                    "Per-Session High ($)",
                    min_value=0.0,
                    step=25.0,
                    key=f"row_{row_id}_per_session_high",
                )

        volume_label = (
            "Monthly Treatments Performed"
            if pricing_mode == "per_session"
            else "Monthly New Patients Starting Program"
        )

        volume = st.number_input(
            volume_label,
            min_value=0,
            step=1,
            key=f"row_{row_id}_volume",
        )

        calc = calculate_row(
            record=record,
            pricing_mode=pricing_mode,
            sessions=int(st.session_state[f"row_{row_id}_sessions"]),
            package_low=float(st.session_state[f"row_{row_id}_package_low"]),
            package_high=float(st.session_state[f"row_{row_id}_package_high"]),
            per_session_low=float(st.session_state[f"row_{row_id}_per_session_low"]),
            per_session_high=float(st.session_state[f"row_{row_id}_per_session_high"]),
            volume=int(volume),
        )

        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)

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

        if float(record.get("consumable_per_session", 0)) > 0:
            st.caption(
                f"Behind-the-scenes consumable assumption: {money(float(record['consumable_per_session']))} per applicable treatment session."
            )
        else:
            st.caption("Behind-the-scenes consumable assumption: no direct consumable cost applied.")

    return calc


def main() -> None:
    df = load_presets()
    init_state(df)
    inject_css()

    st.title(APP_TITLE)
    st.markdown(APP_SUBTITLE)

    st.markdown(
        """
        <div class="top-note">
            Select treatments one row at a time. Changing the treatment will auto-load the preset sessions,
            package pricing, and per-session pricing for that treatment. This tool is for internal planning only
            and is not a guarantee of profitability.
        </div>
        """,
        unsafe_allow_html=True,
    )

    header_cols = st.columns([2.2, 1])
    with header_cols[0]:
        st.subheader("Treatments")
        st.markdown(
            "<div class='small-muted'>All presets are listed together. The treatment pillar appears in each label.</div>",
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("+ Add Another Treatment", on_click=add_row, use_container_width=True)

    all_results: list[dict] = []

    for row_id in st.session_state.row_ids:
        result = render_row(row_id)
        if result is not None:
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
        render_summary_card(
            "Total Monthly Gross Revenue",
            f"{money(gross_low)} – {money(gross_high)}",
        )
    with summary_cols[1]:
        render_summary_card(
            "Total Monthly Direct Consumable Cost",
            money(total_consumable),
        )
    with summary_cols[2]:
        render_summary_card(
            "Total Monthly Adjusted Revenue",
            f"{money(adjusted_low)} – {money(adjusted_high)}",
        )
    with summary_cols[3]:
        render_summary_card(
            "Annualized Adjusted Revenue",
            f"{money(annual_low)} – {money(annual_high)}",
        )

    with st.expander("Optional Finance Input"):
        finance_payment = st.number_input(
            "Monthly Finance Payment ($)",
            min_value=0.0,
            step=50.0,
            value=0.0,
        )

        post_finance_low = adjusted_low - finance_payment
        post_finance_high = adjusted_high - finance_payment

        finance_cols = st.columns(2)
        with finance_cols[0]:
            render_summary_card("Monthly Finance Payment", money(finance_payment))
        with finance_cols[1]:
            render_summary_card(
                "Post-Finance Monthly Adjusted Revenue",
                f"{money(post_finance_low)} – {money(post_finance_high)}",
            )

    st.caption(
        "Internal planning estimate only. Excludes taxes, provider compensation, overhead, marketing allocation, labor allocation, and other operating costs unless modeled elsewhere."
    )


if __name__ == "__main__":
    main()
