"""
Unified ledger response formatter for WhatsApp messages.

Used by both the Processor (image-based) and Orchestrator (voice/text-based)
to produce a consistent item-wise ledger template.
"""

from typing import List, Dict, Any, Optional

# Reference market prices (Rs/kg) — single source of truth
MARKET_PRICES: Dict[str, Dict[str, Any]] = {
    'onion':     {'min': 8,  'max': 35,  'avg': 20},
    'wheat':     {'min': 22, 'max': 28,  'avg': 25},
    'rice':      {'min': 25, 'max': 45,  'avg': 35},
    'cotton':    {'min': 55, 'max': 75,  'avg': 65},
    'soybean':   {'min': 40, 'max': 55,  'avg': 48},
    'grape':     {'min': 30, 'max': 80,  'avg': 50},
    'tomato':    {'min': 10, 'max': 40,  'avg': 22},
    'sugarcane': {'min': 3,  'max': 4,   'avg': 3.5},
    'jowar':     {'min': 25, 'max': 40,  'avg': 32},
    'bajra':     {'min': 20, 'max': 30,  'avg': 25},
    'tur':       {'min': 70, 'max': 110, 'avg': 90},
    'potato':    {'min': 10, 'max': 25,  'avg': 18},
    'chilli':    {'min': 80, 'max': 200, 'avg': 130},
    'turmeric':  {'min': 80, 'max': 150, 'avg': 110},
}


def get_market_ref(crop_type: str) -> Optional[Dict[str, Any]]:
    """Look up market price data for a crop."""
    return MARKET_PRICES.get(crop_type.lower().strip()) if crop_type else None


def _fmt(val, unit='', is_currency=False):
    """Format a field value — returns 'Not detected' for missing/zero values."""
    if val is None:
        return 'Not detected'
    if isinstance(val, (int, float)) and val == 0:
        return 'Not detected'
    if isinstance(val, str) and not val.strip():
        return 'Not detected'
    if isinstance(val, str) and val.lower() in ('unknown', 'none', 'n/a', '0'):
        return 'Not detected'
    if is_currency:
        return f"₹{val:,.2f}" if isinstance(val, float) else f"₹{val}"
    if unit and isinstance(val, float):
        return f"{val:g}{unit}"
    return f"{val}{unit}"


def _is_price_suspicious(price: float, crop_type: str) -> bool:
    """Check if price is outside the expected market range for a crop."""
    ref = get_market_ref(crop_type)
    if not ref or price <= 0:
        return False
    # Allow 20% tolerance outside range
    return price < ref['min'] * 0.8 or price > ref['max'] * 1.2


# ─── i18n labels ───
_LABELS = {
    'en': {
        'header_single': '✅ *Ledger Processed Successfully*',
        'header_multi': '✅ *Ledgers Processed Successfully*',
        'items_saved': '📋 *{n} transactions saved*',
        'txn_id': '📋 *Transaction ID:*',
        'crop': '• Crop Type:',
        'quantity': '• Quantity:',
        'price': '• Price:',
        'total': '• Total:',
        'moisture': '• Moisture:',
        'quality': '• Quality Grade:',
        'date': '• Date:',
        'source': '• Source:',
        'grand_total': '💰 *Grand Total:*',
        'market_ref': '💰 *Market Reference Price ({crop}):* ₹{min}-{max}/kg (avg ₹{avg}/kg)',
        'not_detected': 'ℹ️ *Could not detect:* {fields}',
        'reply_hint': "💬 Reply with missing values to update (e.g. 'Price is ₹20/kg')",
        'saved': 'Your data has been saved to the system.',
        'source_voice': '🎤 Voice message',
        'source_image': '📷 Ledger image',
        'source_text': '⌨️ Text message',
        'price_per_kg': '/kg',
    },
    'hi-IN': {
        'header_single': '✅ *खाता सफलतापूर्वक संसाधित*',
        'header_multi': '✅ *खाते सफलतापूर्वक संसाधित*',
        'items_saved': '📋 *{n} लेनदेन सहेजे गए*',
        'txn_id': '📋 *लेनदेन ID:*',
        'crop': '• फसल प्रकार:',
        'quantity': '• मात्रा:',
        'price': '• मूल्य:',
        'total': '• कुल:',
        'moisture': '• नमी:',
        'quality': '• गुणवत्ता ग्रेड:',
        'date': '• तारीख:',
        'source': '• स्रोत:',
        'grand_total': '💰 *कुल योग:*',
        'market_ref': '💰 *बाजार संदर्भ मूल्य ({crop}):* ₹{min}-{max}/kg (औसत ₹{avg}/kg)',
        'not_detected': 'ℹ️ *पहचान नहीं हो सकी:* {fields}',
        'reply_hint': "💬 छूटी जानकारी अपडेट करने के लिए जवाब दें (जैसे 'कीमत ₹20/kg है')",
        'saved': 'आपका डेटा सिस्टम में सहेजा गया है।',
        'source_voice': '🎤 आवाज संदेश',
        'source_image': '📷 बही छवि',
        'source_text': '⌨️ टेक्स्ट संदेश',
        'price_per_kg': '/kg',
    },
    'mr-IN': {
        'header_single': '✅ *खाते यशस्वीरित्या प्रक्रिया केली*',
        'header_multi': '✅ *खाती यशस्वीरित्या प्रक्रिया केली*',
        'items_saved': '📋 *{n} व्यवहार जतन केले*',
        'txn_id': '📋 *व्यवहार ID:*',
        'crop': '• पीक प्रकार:',
        'quantity': '• प्रमाण:',
        'price': '• किंमत:',
        'total': '• एकूण:',
        'moisture': '• ओलावा:',
        'quality': '• गुणवत्ता ग्रेड:',
        'date': '• तारीख:',
        'source': '• स्रोत:',
        'grand_total': '💰 *एकूण:*',
        'market_ref': '💰 *बाजार संदर्भ किंमत ({crop}):* ₹{min}-{max}/kg (सरासरी ₹{avg}/kg)',
        'not_detected': 'ℹ️ *ओळखता आले नाही:* {fields}',
        'reply_hint': "💬 गहाळ माहिती अपडेट करण्यासाठी उत्तर द्या (उदा. 'किंमत ₹20/kg आहे')",
        'saved': 'तुमचा डेटा सिस्टममध्ये जतन केला आहे।',
        'source_voice': '🎤 ध्वनि संदेश',
        'source_image': '📷 बही प्रतिमा',
        'source_text': '⌨️ मजकूर संदेश',
        'price_per_kg': '/kg',
    },
    'ta-IN': {
        'header_single': '✅ *கணக்கு வெற்றிகரமாக செயலாக்கப்பட்டது*',
        'header_multi': '✅ *கணக்குகள் வெற்றிகரமாக செயலாக்கப்பட்டன*',
        'items_saved': '📋 *{n} பரிவர்த்தனைகள் சேமிக்கப்பட்டன*',
        'txn_id': '📋 *பரிவர்த்தனை ID:*',
        'crop': '• பயிர் வகை:',
        'quantity': '• அளவு:',
        'price': '• விலை:',
        'total': '• மொத்தம்:',
        'moisture': '• ஈரப்பதம்:',
        'quality': '• தர தரம்:',
        'date': '• தேதி:',
        'source': '• ஆதாரம்:',
        'grand_total': '💰 *மொத்தம்:*',
        'market_ref': '💰 *சந்தை குறிப்பு விலை ({crop}):* ₹{min}-{max}/kg (சராசரி ₹{avg}/kg)',
        'not_detected': 'ℹ️ *கண்டறிய முடியவில்லை:* {fields}',
        'reply_hint': "💬 விடுபட்ட தகவலை புதுப்பிக்க பதிலளிக்கவும் (எ.கா. 'விலை ₹20/kg')",
        'saved': 'உங்கள் தரவு அமைப்பில் சேமிக்கப்பட்டது.',
        'source_voice': '🎤 குரல் செய்தி',
        'source_image': '📷 கணக்கு படம்',
        'source_text': '⌨️ உரை செய்தி',
        'price_per_kg': '/kg',
    },
}


def _get_labels(language: str) -> dict:
    """Get i18n labels, defaulting to English."""
    # Normalize short codes
    if language in ('hi', 'hi-IN'):
        return _LABELS['hi-IN']
    if language in ('mr', 'mr-IN'):
        return _LABELS['mr-IN']
    if language in ('ta', 'ta-IN'):
        return _LABELS['ta-IN']
    return _LABELS['en']


def format_ledger_response(
    items: List[Dict[str, Any]],
    language: str = 'en',
    source: str = 'image',
) -> str:
    """
    Format one or more ledger items into a unified WhatsApp message.

    Each item dict should have:
        transaction_id: str
        crop_type: str
        quantity: float          (kg)
        price: float             (₹ per kg, 0 if not detected)
        moisture: float          (%, 0 if not detected)
        quality_grade: str       ('' if not detected)
        date: str                (ISO date)
        farmer_name: str         ('' if not detected)
        fields_needing_review: list[str]   (e.g. ['price', 'moisture'])

    Args:
        items: List of item dicts
        language: Language code
        source: 'voice', 'image', or 'text'

    Returns:
        Formatted WhatsApp message string
    """
    L = _get_labels(language)
    is_multi = len(items) > 1

    # ── Header ──
    header = L['header_multi'] if is_multi else L['header_single']
    lines = [header]
    if is_multi:
        lines.append(L['items_saved'].format(n=len(items)))
    lines.append('')  # blank line

    grand_total = 0.0

    # ── Per-item blocks ──
    for idx, item in enumerate(items, 1):
        crop = item.get('crop_type', 'Unknown')
        qty = float(item.get('quantity', 0))
        price = float(item.get('price', 0))
        moisture = float(item.get('moisture', 0))
        quality = item.get('quality_grade', '')
        dt = item.get('date', '')
        txn_id = item.get('transaction_id', '')
        review_fields = item.get('fields_needing_review', [])

        total = qty * price if qty > 0 and price > 0 else 0
        grand_total += total

        prefix = f"*[{idx}]* " if is_multi else ""

        # Transaction ID
        lines.append(f"{prefix}{L['txn_id']} {txn_id}")

        # Extracted data header (only for single item, multi uses prefix)
        if not is_multi:
            lines.append('')
            lines.append('*Extracted Data:*' if language in ('en',) else
                         '*निकाला गया डेटा:*' if language in ('hi', 'hi-IN') else
                         '*काढलेला डेटा:*' if language in ('mr', 'mr-IN') else
                         '*பிரித்தெடுக்கப்பட்ட தரவு:*' if language in ('ta', 'ta-IN') else
                         '*Extracted Data:*')

        # Fields
        lines.append(f"{L['crop']} {_fmt(crop)}")
        lines.append(f"{L['quantity']} {_fmt(qty, ' kg')}")
        lines.append(f"{L['price']} {_fmt(price, L['price_per_kg'], is_currency=True) if price > 0 else 'Not detected'}")
        lines.append(f"{L['total']} {_fmt(total, '', is_currency=True) if total > 0 else '—'}")
        lines.append(f"{L['moisture']} {_fmt(moisture, '%')}")
        lines.append(f"{L['quality']} {_fmt(quality)}")
        lines.append(f"{L['date']} {_fmt(dt)}")

        # Source
        source_label = L.get(f'source_{source}', L['source_image'])
        lines.append(f"{L['source']} {source_label}")

        # ── Market reference logic ──
        ref = get_market_ref(crop)
        if ref and crop.lower() not in ('unknown', ''):
            if price == 0:
                # Price missing → show ref + "could not detect" + reply hint
                lines.append('')
                lines.append(L['market_ref'].format(
                    crop=crop, min=ref['min'], max=ref['max'], avg=ref['avg']))
                # Build missing fields list
                missing = [f.lower() for f in review_fields] if review_fields else ['price']
                lines.append(L['not_detected'].format(fields=', '.join(missing)))
                lines.append(L['reply_hint'])
            elif _is_price_suspicious(price, crop):
                # Price present but looks off → show ref as suggestion
                lines.append('')
                lines.append(L['market_ref'].format(
                    crop=crop, min=ref['min'], max=ref['max'], avg=ref['avg']))
        elif review_fields:
            # No market ref available but has missing fields
            missing = [f.lower() for f in review_fields]
            lines.append('')
            lines.append(L['not_detected'].format(fields=', '.join(missing)))
            lines.append(L['reply_hint'])

        lines.append('')  # blank line between items

    # ── Grand total for multi-item ──
    if is_multi and grand_total > 0:
        lines.append(f"{L['grand_total']} ₹{grand_total:,.2f}")
        lines.append('')

    # ── Footer ──
    lines.append(L['saved'])

    return '\n'.join(lines)
