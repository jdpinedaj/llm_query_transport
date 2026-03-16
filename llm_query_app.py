# uv run streamlit run llm_query_app.py --server.headless=true

# Standard Libraries

# External Libraries
import streamlit as st

# Local Imports
from src.config.settings import LoadConfig
from src.infrastructure.ui.streamlit_helpers import (
    clear_chat_and_restart,
    initialize_session_states,
    manage_messages,
    render_chat_message,
)
from src.infrastructure.ui.streamlit_orchestrator import execute_all_in_chat


@st.cache_resource
def get_config():
    return LoadConfig()


APPCFG = get_config()
DATABASE_URI = APPCFG.database_uri


# Configure Streamlit page layout
st.set_page_config(
    page_title=APPCFG.page_title,
    page_icon=APPCFG.page_icon,
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    f"""
    <style>
        /* Chat message alignment */
        .st-emotion-cache-1c7y2kd {{
            flex-direction: row-reverse;
            text-align: right;
        }}
        /* Remove page scroll - only internal container scrolls */
        .main {{
            overflow: hidden;
        }}
        /* Add margins to content - centered layout */
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 3rem;
            max-width: {APPCFG.max_container_width};
            margin-left: auto;
            margin-right: auto;
            padding-left: 4rem;
            padding-right: 4rem;
        }}
        /* Make columns look better */
        [data-testid="column"] {{
            padding: 0.5rem;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)


def main():
    # Ensure all session states are initialized
    initialize_session_states()

    # Start conversation automatically if it's the first user interaction
    if not st.session_state["chat_history"]:
        manage_messages("assistant", APPCFG.welcome_message, "assistant")

    # LOGO: Top-left corner
    st.image(image=APPCFG.logo_image, width=APPCFG.logo_width)

    # CONTAINER A: Main centered container
    _, container_a, _ = st.columns(APPCFG.outer_columns)

    with container_a:
        # CONTAINER B: Top section with two boxes side by side
        col_left, col_right = st.columns(APPCFG.content_columns, gap="large")

        # Left box: Database Info & Quick Queries
        with col_left, st.container(border=True):
            st.markdown("### 📝 Database Info")
            with st.container(height=APPCFG.container_height):
                st.markdown(
                    """
                    **Available tables:**
                    - `station` — id, name, lat, long, dock_count, city, installation_date
                    - `status` — station_id, bikes_available, docks_available, time
                    - `trip` — id, duration, start_date, start_station_id, end_date, end_station_id, bike_id, subscription_type, zip_code
                    - `weather` — date, temperatures, humidity, visibility, wind, precipitation, cloud_cover, events, zip_code

                    **Example queries:**
                    - Get the average duration of trips grouped by zip codes
                    - How many trips started from station 63?
                    - What was the maximum temperature on 8/29/2013 for zip code 94107?
                    - List all stations in San Jose with their dock counts
                    - How did weather events impact ridership in August 2015?
                    """,
                )

        # Right box: Request History
        with col_right, st.container(border=True):
            st.markdown("### 📋 Request History")
            with st.container(height=APPCFG.container_height):
                for message in st.session_state["chat_history"]:
                    render_chat_message(message)

        # Initialize user_query in session state if it doesn't exist
        if "user_query" not in st.session_state:
            st.session_state["user_query"] = APPCFG.default_query

        # CONTAINER C: Bottom section with text input and buttons (centered and narrower)
        _, container_c, _ = st.columns(APPCFG.input_columns)

        with container_c:
            # CONTAINER D: Text input area
            with st.container(border=True):
                st.markdown("### ✏️ Your Request")
                user_input = st.text_area(
                    "Enter your request:",
                    key="user_query",
                    height=APPCFG.input_height,
                    label_visibility="collapsed",
                )

            # CONTAINER E: Buttons centered
            _, col_btn_left, col_btn_right, _ = st.columns(APPCFG.button_columns)
            with col_btn_left:
                if st.button("🔄 Clear History and Restart", use_container_width=True):
                    clear_chat_and_restart()
            with col_btn_right:
                if st.button("🚀 Submit", use_container_width=True) and user_input:
                    with st.spinner(APPCFG.spinner_text):
                        execute_all_in_chat(user_input, APPCFG, DATABASE_URI)

        # Add white space at the bottom
        st.markdown("<br><br><br>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
