
import math
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="EndyMed PRO MAX Practice Revenue Planner",
    page_icon="💜",
    layout="wide",
)

APP_TITLE = "EndyMed PRO MAX Practice Revenue Planner"
APP_SUBTITLE = (
    "Internal sales planning tool for modeling treatment revenue across multiple PRO MAX offerings."
)

SECTION_CONFIG = {
    "Face T+C": {"label": "Face T+C Treatments", "max_rows": 3, "key": "face"},
    "Body T+C": {"label": "Body T+C Treatments", "max_rows": 3, "key": "body"},
    "Fractional": {"label": "Fractional Treatments", "max_rows": 2, "key": "fractional"},
    "Combo": {"label": "Combo Treatments", "max_rows": 4, "key": "combo"},
}

DATA_PATH = Path(__file__).with_name("presets.csv")


@st.cache_data
def load_presets() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df = df[df["active_in_app"].astype(str).str.lower() == "yes"].copy()
    df["display_order"] = pd.to_numeric(df["display_order"], errors="coerce").fillna(999)
    numeric_cols = [
        "sessions_default",
        "package_low",
        "package_high",
        "per_session_low",
        "per_session_high",
        "consumable_per_session",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["pricing_mode_default"] = df["pricing_mode_default"].astype(str).str.lower().replace({"nan": "package"})
    df["combo_consumable_mode"] = df["combo_consumable_mode"].fillna("none").astype(str)
    return df.sort_values(["section", "display_order", "preset_name"])


def money(value: float) -> str:
    return f"${value:,.0f}"


def init_row_counts() -> None:
    for section, config in SECTION_CONFIG.items():
        state_key = f"row_count_{config['key']}"
        if state_key not in st.session_state:
            st.session_state[state_key] = 1


def add_row(section_key: str, max_rows: int) -> None:
    state_key = f"row_count_{section_key}"
    if st.session_state[state_key] < max_rows:
        st.session_state[state_key] += 1


def section_df(df: pd.DataFrame, section: str) -> pd.DataFrame:
    subset = df[df["section"] == section].copy()
    return subset.sort_values(["display_order", "preset_name"])


def get_preset_record(subset: pd.DataFrame, preset_name: str) -> dict:
    record = subset[subset["preset_name"] == preset_name].iloc[0]
    return record.to_dict()


def initialize_row_defaults(row_key: str, record: dict) -> None:
    defaults = {
        f"{row_key}_pricing_mode": record["pricing_mode_default"] if record["pricing_mode_default"] in {"package", "per_session"} else "package",
        f"{row_key}_sessions": int(record["sessions_default"]),
        f"{row_key}_package_low": float(record["package_low"]),
        f"{row_key}_package_high": float(record["package_high"]),
        f"{row_key}_per_session_low": float(record["per_session_low"]),
        f"{row_key}_per_session_high": float(record["per_session_high"]),
        f"{row_key}_volume": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def sync_defaults_when_preset_changes(row_key: str, record: dict, changed: bool) -> None:
    if not changed:
        return
    st.session_state[f"{row_key}_pricing_mode"] = record["pricing_mode_default"] if record["pricing_mode_default"] in {"package", "per_session"} else "package"
    st.session_state[f"{row_key}_sessions"] = int(record["sessions_default"])
    st.session_state[f"{row_key}_package_low"] = float(record["package_low"])
    st.session_state[f"{row_key}_package_high"] = float(record["package_high"])
    st.session_state[f"{row_key}_per_session_low"] = float(record["per_session_low"])
    st.session_state[f"{row_key}_per_session_high"] = float(record["per_session_high"])


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
        "preset_name": record["preset_name"],
        "section": record["section"],
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
    }


def render_row(subset: pd.DataFrame, section_name: str, section_key: str, row_idx: int) -> dict | None:
    preset_names = subset["preset_name"].tolist()
    row_key = f"{section_key}_{row_idx}"
    selected_key = f"{row_key}_selected"

    if selected_key not in st.session_state:
        st.session_state[selected_key] = preset_names[0]

    previous_selected = st.session_state[selected_key]
    selected = st.selectbox(
        "Treatment Preset",
        options=preset_names,
        key=selected_key,
        label_visibility="collapsed",
    )
    record = get_preset_record(subset, selected)
    initialize_row_defaults(row_key, record)
    sync_defaults_when_preset_changes(row_key, record, changed=(selected != previous_selected))

    mode_map = {"Package Pricing": "package", "Per Session Pricing": "per_session"}
    reverse_mode_map = {v: k for k, v in mode_map.items()}
    current_mode = st.session_state.get(f"{row_key}_pricing_mode", "package")
    mode_label = st.radio(
        "Pricing Mode",
        options=list(mode_map.keys()),
        horizontal=True,
        index=list(mode_map.values()).index(current_mode if current_mode in mode_map.values() else "package"),
        key=f"{row_key}_pricing_mode_ui",
    )
    pricing_mode = mode_map[mode_label]
    st.session_state[f"{row_key}_pricing_mode"] = pricing_mode

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        sessions = st.number_input(
            "Sessions per Package",
            min_value=1,
            step=1,
            key=f"{row_key}_sessions",
            disabled=(pricing_mode == "per_session"),
        )
    with col2:
        if pricing_mode == "package":
            low_value = st.number_input("Package Low ($)", min_value=0.0, step=50.0, key=f"{row_key}_package_low")
        else:
            low_value = st.number_input("Per-Session Low ($)", min_value=0.0, step=25.0, key=f"{row_key}_per_session_low")
    with col3:
        if pricing_mode == "package":
            high_value = st.number_input("Package High ($)", min_value=0.0, step=50.0, key=f"{row_key}_package_high")
        else:
            high_value = st.number_input("Per-Session High ($)", min_value=0.0, step=25.0, key=f"{row_key}_per_session_high")

    volume_label = "Monthly Treatments Performed" if pricing_mode == "per_session" else "Monthly New Patients Starting Program"
    volume = st.number_input(volume_label, min_value=0, step=1, key=f"{row_key}_volume")

    package_low = st.session_state[f"{row_key}_package_low"]
    package_high = st.session_state[f"{row_key}_package_high"]
    per_session_low = st.session_state[f"{row_key}_per_session_low"]
    per_session_high = st.session_state[f"{row_key}_per_session_high"]

    calc = calculate_row(
        record=record,
        pricing_mode=pricing_mode,
        sessions=int(sessions),
        package_low=float(package_low),
        package_high=float(package_high),
        per_session_low=float(per_session_low),
        per_session_high=float(per_session_high),
        volume=int(volume),
    )

    with st.container(border=True):
        a, b, c = st.columns(3)
        a.metric("Monthly Gross Revenue", f"{money(calc['monthly_gross_low'])} – {money(calc['monthly_gross_high'])}")
        b.metric("Monthly Direct Consumable Cost", money(calc["monthly_consumable"]))
        c.metric("Monthly Adjusted Revenue", f"{money(calc['monthly_adjusted_low'])} – {money(calc['monthly_adjusted_high'])}")
        st.caption(
            f"Annual adjusted revenue: {money(calc['annual_adjusted_low'])} – {money(calc['annual_adjusted_high'])}"
        )
        if float(record["consumable_per_session"]) > 0:
            st.caption(f"Behind-the-scenes consumable assumption: {money(float(record['consumable_per_session']))} per applicable treatment session.")
        else:
            st.caption("Behind-the-scenes consumable assumption: no direct consumable cost applied.")

    return calc


def render_section(df: pd.DataFrame, section_name: str, config: dict) -> list[dict]:
    subset = section_df(df, section_name)
    results: list[dict] = []
    state_key = f"row_count_{config['key']}"

    with st.container():
        st.subheader(config["label"])
        st.caption("Select one or more presets, then adjust pricing and volume as needed.")
        for row_idx in range(st.session_state[state_key]):
            with st.container(border=True):
                st.markdown(f"**{config['label']} — Row {row_idx + 1}**")
                calc = render_row(subset, section_name, config["key"], row_idx)
                if calc:
                    results.append(calc)
        if st.session_state[state_key] < config["max_rows"]:
            st.button(
                f"+ Add Another Treatment to {config['label']}",
                key=f"add_{config['key']}",
                on_click=add_row,
                args=(config["key"], config["max_rows"]),
            )
        else:
            st.caption(f"Maximum rows reached for {config['label']}.")
    return results


def total_range(results: list[dict], key_low: str, key_high: str) -> tuple[float, float]:
    return (sum(r[key_low] for r in results), sum(r[key_high] for r in results))


def main() -> None:
    st.title(APP_TITLE)
    st.markdown(APP_SUBTITLE)
    st.info(
        "Use preset pricing and sessions as your starting point, then override values when a prospect has a more defined strategy. "
        "This tool is for internal planning only and is not a profitability guarantee."
    )

    init_row_counts()
    df = load_presets()

    all_results: list[dict] = []
    for section_name, config in SECTION_CONFIG.items():
        all_results.extend(render_section(df, section_name, config))
        st.divider()

    gross_low, gross_high = total_range(all_results, "monthly_gross_low", "monthly_gross_high")
    adjusted_low, adjusted_high = total_range(all_results, "monthly_adjusted_low", "monthly_adjusted_high")
    annual_low, annual_high = total_range(all_results, "annual_adjusted_low", "annual_adjusted_high")
    total_consumable = sum(r["monthly_consumable"] for r in all_results)

    st.header("Total Practice Revenue Summary")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Monthly Gross Revenue", f"{money(gross_low)} – {money(gross_high)}")
    k2.metric("Total Monthly Direct Consumable Cost", money(total_consumable))
    k3.metric("Total Monthly Adjusted Revenue", f"{money(adjusted_low)} – {money(adjusted_high)}")
    k4.metric("Annualized Adjusted Revenue", f"{money(annual_low)} – {money(annual_high)}")

    with st.expander("Advanced Planning Inputs (Optional)"):
        finance_payment = st.number_input("Monthly Finance Payment ($)", min_value=0.0, step=50.0, value=0.0)
        other_opex = st.number_input(
            "Other Monthly Operating Expenses ($)",
            min_value=0.0,
            step=50.0,
            value=0.0,
            help="Use this for optional planning inputs such as EndyMed-only marketing, labor allocation, or space allocation.",
        )
        post_finance_low = adjusted_low - finance_payment
        post_finance_high = adjusted_high - finance_payment
        post_finance_opex_low = adjusted_low - finance_payment - other_opex
        post_finance_opex_high = adjusted_high - finance_payment - other_opex

        c1, c2 = st.columns(2)
        c1.metric("Post-Finance Monthly Adjusted Revenue", f"{money(post_finance_low)} – {money(post_finance_high)}")
        c2.metric(
            "Post-Finance & Opex Monthly Adjusted Revenue",
            f"{money(post_finance_opex_low)} – {money(post_finance_opex_high)}",
        )

    if all_results:
        with st.expander("Scenario Detail Table"):
            detail_df = pd.DataFrame(all_results)[[
                "section",
                "preset_name",
                "pricing_mode",
                "sessions",
                "volume",
                "monthly_gross_low",
                "monthly_gross_high",
                "monthly_consumable",
                "monthly_adjusted_low",
                "monthly_adjusted_high",
                "annual_adjusted_low",
                "annual_adjusted_high",
            ]]
            st.dataframe(detail_df, use_container_width=True)

    st.caption(
        "Internal planning estimate only. Excludes taxes, provider compensation, overhead, and other operating costs unless manually entered."
    )


if __name__ == "__main__":
    main()
