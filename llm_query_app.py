# poetry run streamlit run llm_query_app.py --server.headless=true

#! Imports
#  External libraries
import streamlit as st
from PIL import Image

# Local imports
from src.load_config import LoadConfig
from src.utils import execute_all_in_chat
from src.sub_utils import (
    _download_data_csv,
    _initialize_session_states,
    _manage_messages,
    _clear_chat_and_restart,
    _get_external_ip,
)

APPCFG = LoadConfig()


st.markdown(
    """
        <style>
            .st-emotion-cache-1c7y2kd {
                flex-direction: row-reverse;
                text-align: right;
            }
        </style>
        """,
    unsafe_allow_html=True,
)


#! Main function
def main():

    # Checking the external IP address
    external_ip = _get_external_ip()
    st.write(f"Streamlit server external IP: {external_ip}")

    # Load the image and resize it with a fixed height
    original_image = Image.open("images/upv-logo.png")
    fixed_height = 100  # Set your desired height
    width_ratio = fixed_height / original_image.height
    new_width = int(original_image.width * width_ratio)
    resized_image = original_image.resize((new_width, fixed_height))
    st.image(resized_image, use_container_width=False)
    # st.divider()

    with st.container(border=True):
        st.markdown(" #### 📧 Chat history")

        # Ensure all session states are initialized
        _initialize_session_states()

        # Start conversation automatically if it's the first user interaction, and say something about if the request is related to locations, brands or top categories?
        if not st.session_state["chat_history"]:
            _manage_messages(
                "assistant",
                "Hello! Please use the options below to refine your query. You can select the criteria you want to include in your query.",
                "assistant",
            )

        # Display previous chat messages in a scrollable container
        with st.container(height=1000):
            for message in st.session_state["chat_history"]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # st.divider()

    #! User input for query refinement
    with st.container(border=True):
        #! User input for natural language query
        # User input for natural language query, starting with a default value
        default_query = "Get the average duration of trips grouped by zip codes"
        user_input = st.text_area(
            " #### ✏️ Enter your request", value=default_query, key="user_query"
        )

        if st.button("Submit"):
            if user_input:
                # Process the user input within a spinner to indicate thinking/loading
                with st.spinner("Thinking..."):
                    execute_all_in_chat(user_input)
                    # execute_test_query(user_input)

    # Creating a spacer and the restart button at the bottom
    with st.container(border=True):
        col1, col2, col3 = st.columns([0.3, 0.4, 0.3])

        with col1:
            _download_data_csv()

        with col3:
            if st.button("Clear Chat and Restart"):
                _clear_chat_and_restart()


if __name__ == "__main__":
    main()
