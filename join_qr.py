"""QR code for a batch's join code: the phone's camera opens the student app on the Join screen."""
from io import BytesIO

import segno


def make_join_qr(code):
    """Return the student deep link and an inline, high-contrast QR SVG."""
    url = f"campus-connect://join?code={code}"
    output = BytesIO()
    segno.make_qr(url).save(output, kind="svg", scale=4, light="#fff", xmldecl=False,
                            title="QR code to join this batch")
    return url, output.getvalue().decode("utf-8")
