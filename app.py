import streamlit as st

from detector import analyze_payment


st.set_page_config(
    page_title="PayVerify",
    page_icon="💳",
    layout="wide"
)


st.title("💳 PayVerify")

st.subheader(
    "Fake Payment Screenshot Detector"
)

st.write(
    "Upload a payment screenshot and "
    "check for suspicious indicators."
)

st.warning(
    "⚠️ This is an educational prototype. "
    "A screenshot alone cannot confirm an actual payment."
)


uploaded_file = st.file_uploader(
    "📤 Upload Payment Screenshot",
    type=[
        "png",
        "jpg",
        "jpeg"
    ]
)


if uploaded_file is not None:

    st.image(
        uploaded_file,
        caption="Uploaded Payment Screenshot",
        use_container_width=True
    )


    if st.button(
        "🔍 Analyze Screenshot"
    ):

        with st.spinner(
            "Analyzing screenshot..."
        ):

            result = analyze_payment(
                uploaded_file
            )


        st.divider()

        st.header(
            "📊 Analysis Result"
        )


        # Result
        if result["result"] == "SUSPICIOUS":

            st.error(
                "🚨 SUSPICIOUS PAYMENT SCREENSHOT"
            )

        elif result["result"] == "NEEDS VERIFICATION":

            st.warning(
                "⚠️ PAYMENT NEEDS VERIFICATION"
            )

        else:

            st.success(
                "✅ LIKELY GENUINE"
            )


        # Information
        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "Risk Score",
                f"{result['risk_score']}%"
            )


        with col2:

            st.metric(
                "Amount",
                result["amount"]
            )


        with col3:

            st.metric(
                "UTR / Transaction ID",
                result["utr"]
            )


        st.divider()


        st.subheader(
            "🧠 Why?"
        )


        if result["reasons"]:

            for reason in result["reasons"]:

                st.write(
                    "⚠️ " + reason
                )

        else:

            st.success(
                "No major suspicious indicators detected."
            )


        st.divider()


        with st.expander(
            "📄 View Extracted Text"
        ):

            st.write(
                result["text"]
            )