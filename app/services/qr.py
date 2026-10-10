import logging

log = logging.getLogger("qr")


def qr_svg(url):
    """Returns inline SVG markup for a QR code, or '' if the segno package is missing."""
    try:
        import segno
        return segno.make(url, error="m").svg_inline(scale=4, border=1, dark="#0A2A6B")
    except Exception as err:  # the ID card still works with the verification link alone
        log.warning("QR code not generated: %s", type(err).__name__)
        return ""
