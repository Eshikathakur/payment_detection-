import cv2
import pytesseract
import re
import numpy as np
from PIL import Image
import io


# ============================================================
# TESSERACT LOCATION
# ============================================================

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = text.replace("\r", "\n")
    text = text.replace("\xa0", " ")

    # Keep new lines because they help identify payment amount
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


# ============================================================
# OPEN IMAGE
# Supports Streamlit UploadedFile
# ============================================================

def open_image_safely(image):

    # PIL Image
    if isinstance(image, Image.Image):
        return image.convert("RGB")

    # File path
    if isinstance(image, str):
        return Image.open(image).convert("RGB")

    # Streamlit UploadedFile
    if hasattr(image, "read"):

        try:
            image.seek(0)
        except Exception:
            pass

        data = image.read()

        return Image.open(
            io.BytesIO(data)
        ).convert("RGB")

    # Bytes
    if isinstance(image, bytes):

        return Image.open(
            io.BytesIO(image)
        ).convert("RGB")

    raise ValueError(
        "Unsupported image format."
    )


# ============================================================
# CREATE OCR IMAGES
# ============================================================

def create_ocr_images(pil_image):

    img = np.array(
        pil_image.convert("RGB")
    )

    img = cv2.cvtColor(
        img,
        cv2.COLOR_RGB2BGR
    )

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )

    # Bigger image
    gray = cv2.resize(
        gray,
        None,
        fx=3,
        fy=3,
        interpolation=cv2.INTER_CUBIC
    )

    # Slight blur
    blur = cv2.GaussianBlur(
        gray,
        (3, 3),
        0
    )

    # OTSU
    otsu = cv2.threshold(
        blur,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    # Adaptive threshold
    adaptive = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    # Sharpen
    kernel = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ])

    sharpened = cv2.filter2D(
        gray,
        -1,
        kernel
    )

    return [
        img,
        gray,
        otsu,
        adaptive,
        sharpened
    ]


# ============================================================
# EXTRACT TEXT
# ============================================================

def extract_text(image):

    pil_image = open_image_safely(
        image
    )

    images = create_ocr_images(
        pil_image
    )

    all_text = []

    configs = [
        "--psm 6",
        "--psm 11",
        "--psm 12"
    ]

    for img in images:

        for config in configs:

            try:

                text = pytesseract.image_to_string(
                    img,
                    config=config
                )

                if text:
                    all_text.append(text)

            except Exception:
                pass

    text = "\n".join(
        all_text
    )

    return clean_text(
        text
    )


# ============================================================
# EXTRACT AMOUNT
# ============================================================

def extract_amount(text):

    if not text:
        return None

    original_text = text

    # --------------------------------------------------------
    # Normalize OCR mistakes
    # --------------------------------------------------------

    text = text.replace(
        "₹",
        "₹"
    )

    text = text.replace(
        "Rs.",
        "Rs"
    )

    text = text.replace(
        "rs.",
        "Rs"
    )

    text_lower = text.lower()


    candidates = []


    # ========================================================
    # 1. DIRECT CURRENCY AMOUNT
    # ========================================================

    currency_patterns = [

        # ₹250
        r"₹\s*([0-9]{1,9}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",

        # Rs 250
        r"\brs\s*[:.]?\s*([0-9]{1,9}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",

        # INR 250
        r"\binr\s*[:.]?\s*([0-9]{1,9}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
    ]


    for pattern in currency_patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for value in matches:

            try:

                amount = float(
                    value.replace(",", "")
                )

                if 1 <= amount <= 10000000:

                    candidates.append(
                        amount
                    )

            except Exception:
                pass


    # ========================================================
    # 2. ₹ ON ONE LINE + NUMBER ON NEXT LINE
    # ========================================================

    lines = original_text.splitlines()

    for i, line in enumerate(lines):

        line_clean = line.strip()

        if "₹" in line_clean:

            # Number on same line
            nums = re.findall(
                r"\b\d{1,9}(?:,\d{3})*(?:\.\d{1,2})?\b",
                line_clean
            )

            for value in nums:

                try:

                    amount = float(
                        value.replace(",", "")
                    )

                    if 1 <= amount <= 10000000:
                        candidates.append(amount)

                except Exception:
                    pass


            # Number on next line
            if i + 1 < len(lines):

                nums = re.findall(
                    r"\b\d{1,9}(?:,\d{3})*(?:\.\d{1,2})?\b",
                    lines[i + 1]
                )

                for value in nums:

                    try:

                        amount = float(
                            value.replace(",", "")
                        )

                        if 1 <= amount <= 10000000:
                            candidates.append(amount)

                    except Exception:
                        pass


    # ========================================================
    # 3. IMPORTANT:
    # PAYMENT SUCCESS SCREEN
    #
    # If OCR loses ₹ and reads:
    #
    # Paid successfully to
    # Rahul Sharma
    # 250
    #
    # detect the nearby number.
    # ========================================================

    payment_keywords = [
        "paid successfully",
        "payment successful",
        "payment to",
        "paid to",
        "amount paid",
        "you paid",
        "sent to",
        "payment"
    ]


    for keyword in payment_keywords:

        position = text_lower.find(
            keyword
        )

        if position != -1:

            # Take nearby text
            nearby = original_text[
                max(0, position - 50):
                position + 500
            ]


            # Find currency amounts first
            nearby_currency = re.findall(
                r"(?:₹|rs\.?|inr)\s*"
                r"([0-9]{1,9}(?:,[0-9]{3})*"
                r"(?:\.[0-9]{1,2})?)",
                nearby,
                flags=re.IGNORECASE
            )


            for value in nearby_currency:

                try:

                    amount = float(
                        value.replace(",", "")
                    )

                    if 1 <= amount <= 10000000:
                        candidates.append(amount)

                except Exception:
                    pass


            # ------------------------------------------------
            # If ₹ was missed by OCR, find plain numbers.
            # ------------------------------------------------

            nearby_numbers = re.findall(
                r"\b\d{1,7}(?:,\d{3})*(?:\.\d{1,2})?\b",
                nearby
            )


            for value in nearby_numbers:

                try:

                    amount = float(
                        value.replace(",", "")
                    )

                    # Ignore obvious time/date values
                    if amount in [
                        2024,
                        2025,
                        2026,
                        2027
                    ]:
                        continue

                    if 1 <= amount <= 100000:

                        candidates.append(
                            amount
                        )

                except Exception:
                    pass


    # ========================================================
    # 4. LOOK FOR LARGE CURRENCY-LIKE NUMBERS
    # ========================================================

    # OCR sometimes changes ₹ to R or another character.

    weird_currency_patterns = [

        r"\bR\s*([0-9]{1,9}(?:,[0-9]{3})*)",

        r"\bRs\s*([0-9]{1,9}(?:,[0-9]{3})*)",

        r"\bINR\s*([0-9]{1,9}(?:,[0-9]{3})*)"
    ]


    for pattern in weird_currency_patterns:

        matches = re.findall(
            pattern,
            original_text,
            flags=re.IGNORECASE
        )

        for value in matches:

            try:

                amount = float(
                    value.replace(",", "")
                )

                if 1 <= amount <= 10000000:

                    candidates.append(
                        amount
                    )

            except Exception:
                pass


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique = []

    for amount in candidates:

        if amount not in unique:

            unique.append(
                amount
            )


    # ========================================================
    # REMOVE OBVIOUS UTR NUMBERS
    # ========================================================

    filtered = []

    for amount in unique:

        # Transaction IDs are normally 10+ digits.
        if amount >= 100000000:

            continue

        filtered.append(
            amount
        )


    # ========================================================
    # PREFER COMMON PAYMENT VALUES
    # ========================================================

    if filtered:

        # Prefer values which are associated with
        # payment-related text.

        for amount in filtered:

            amount_str = (
                str(int(amount))
                if amount.is_integer()
                else str(amount)
            )

            payment_context = [
                "paid",
                "payment",
                "amount",
                "sent",
                "successfully"
            ]

            # If number exists close to payment words,
            # give it priority.
            for word in payment_context:

                if word in text_lower:

                    pos = text_lower.find(word)

                    nearby = text_lower[
                        pos:pos + 500
                    ]

                    if amount_str in nearby:

                        return amount


        # Otherwise return first reasonable candidate
        return filtered[0]


    return None


# ============================================================
# EXTRACT UTR / TRANSACTION ID
# ============================================================

def extract_utr(text):

    if not text:
        return None


    patterns = [

        r"(?:UTR|UTR\s*NO|UTR\s*NUMBER)"
        r"\s*[:#\-]?\s*"
        r"([A-Za-z0-9_\-]{6,})",

        r"(?:Transaction\s*ID|Transaction\s*No|"
        r"Txn\s*ID|Txn\s*No)"
        r"\s*[:#\-]?\s*"
        r"([A-Za-z0-9_\-]{6,})",

        r"(?:UPI\s*transaction\s*ID|UPI\s*ID)"
        r"\s*[:#\-]?\s*"
        r"([A-Za-z0-9_\-]{6,})",

        r"(?:Google\s*transaction\s*ID)"
        r"\s*[:#\-]?\s*"
        r"([A-Za-z0-9_\-]{6,})",

        r"(?:Reference\s*No|Reference\s*Number|Ref\s*No)"
        r"\s*[:#\-]?\s*"
        r"([A-Za-z0-9_\-]{6,})"
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            value = match.group(
                1
            ).strip()

            if len(value) >= 6:

                return value


    # ========================================================
    # UPI style ID
    # ========================================================

    upi_pattern = (
        r"\b[A-Za-z0-9]{5,}"
        r"[_\-]"
        r"[A-Za-z0-9]{3,}\b"
    )


    match = re.search(
        upi_pattern,
        text
    )

    if match:

        return match.group(0)


    # ========================================================
    # Long numeric transaction ID
    # ========================================================

    numbers = re.findall(
        r"\b\d{10,20}\b",
        text
    )


    for number in numbers:

        # Ignore years
        if number in [
            "2024012345",
            "2025012345"
        ]:
            continue

        return number


    return None


# ============================================================
# SUSPICIOUS INDICATORS
# ============================================================

def detect_suspicious_indicators(
    text,
    amount,
    utr
):

    reasons = []

    risk_score = 0

    text_lower = (
        text.lower()
        if text
        else ""
    )


    # ========================================================
    # AMOUNT MISSING
    # ========================================================

    if amount is None:

        reasons.append(
            "Payment amount could not be detected."
        )

        risk_score += 20


    # ========================================================
    # UTR MISSING
    # ========================================================

    if utr is None:

        reasons.append(
            "Transaction/UTR number could not be detected."
        )

        risk_score += 15


    # ========================================================
    # SUSPICIOUS STATUS
    # ========================================================

    suspicious_words = [

        "failed",
        "failure",
        "declined",
        "cancelled",
        "canceled",
        "pending",
        "processing",
        "error",
        "invalid",
        "unsuccessful"
    ]


    found_words = []


    for word in suspicious_words:

        if word in text_lower:

            found_words.append(
                word
            )


    if found_words:

        reasons.append(
            "Suspicious payment status detected: "
            + ", ".join(found_words)
        )

        risk_score += 25


    # ========================================================
    # FAKE / EDITED WORDS
    # ========================================================

    fake_words = [

        "edited",
        "modified",
        "sample",
        "demo",
        "test payment",
        "fake"
    ]


    found_fake = []


    for word in fake_words:

        if word in text_lower:

            found_fake.append(
                word
            )


    if found_fake:

        reasons.append(
            "Potentially suspicious wording detected."
        )

        risk_score += 35


    # ========================================================
    # VERY LITTLE TEXT
    # ========================================================

    if len(text.strip()) < 10:

        reasons.append(
            "Very little readable payment information was found."
        )

        risk_score += 15


    # ========================================================
    # LIMIT
    # ========================================================

    risk_score = min(
        risk_score,
        100
    )


    return (
        risk_score,
        reasons
    )


# ============================================================
# ANALYZE PAYMENT
# ============================================================

def analyze_payment(image):

    # OCR
    text = extract_text(
        image
    )


    # Amount
    amount = extract_amount(
        text
    )


    # UTR
    utr = extract_utr(
        text
    )


    # Suspicious indicators
    risk_score, reasons = (
        detect_suspicious_indicators(
            text,
            amount,
            utr
        )
    )


    # ========================================================
    # RESULT
    # ========================================================

    if risk_score >= 60:

        result = "LIKELY FAKE"

    elif risk_score >= 30:

        result = "SUSPICIOUS"

    else:

        result = "LIKELY GENUINE"


    # ========================================================
    # NO REASONS
    # ========================================================

    if not reasons:

        reasons.append(
            "No major suspicious indicators were detected."
        )


    # ========================================================
    # FORMAT AMOUNT
    # ========================================================

    if amount is not None:

        if float(amount).is_integer():

            amount_display = (
                f"₹{int(amount):,}"
            )

        else:

            amount_display = (
                f"₹{amount:,.2f}"
            )

    else:

        amount_display = "Not detected"


    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        "result": result,

        "risk_score": risk_score,

        "amount": amount_display,

        "utr": (
            utr
            if utr
            else "Not detected"
        ),

        "reasons": reasons,

        "text": text
    }