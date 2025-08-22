import streamlit as st
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import easyocr
import numpy as np
import json
import os

st.set_page_config(page_title="Banner QA – Text Zone Validation", layout="wide")

st.title("Banner QA – Text Zone Validation")

# --- File uploader ---
uploaded_file = st.file_uploader("Upload a banner", type=["png", "jpg", "jpeg"])

# --- OCR Reader (cache to avoid reloading) ---
@st.cache_resource
def load_reader():
    return easyocr.Reader(["en", "es", "ko", "ja", "ch_sim", "ch_tra", "ar", "cs", "de", "id", "hu", "ms", "pl", "th", "vi"])
reader = load_reader()

# --- Config Files ---
CONFIG_FILE = "zone_presets.json"
IGNORE_FILE = "ignore_terms.json"
IGNORE_ZONES_FILE = "ignore_zones.json"

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

# --- Loaders/Savers ---
def save_presets(zones): save_json(CONFIG_FILE, zones)
def load_presets(): return load_json(CONFIG_FILE, {})

def save_ignore_terms(terms): save_json(IGNORE_FILE, terms)
def load_ignore_terms(): return load_json(IGNORE_FILE, [])

def save_ignore_zones(zones): save_json(IGNORE_ZONES_FILE, zones)
def load_ignore_zones(): return load_json(IGNORE_ZONES_FILE, [])

# --- Default zones (normalized 0–1) ---
default_zone_defs = {
    "Eyebrow Copy": (0.125, 0.1042, 0.3047, 0.021),
    "Headline Copy": (0.125, 0.1458, 0.3047, 0.1458),
    "Body Copy": (0.125, 0.3027, 0.3047, 0.05),
}

# If preset exists, load and use as defaults
loaded_presets = load_presets()
if loaded_presets:
    default_zone_defs = loaded_presets

st.sidebar.title("⚙️ Zone Settings")

# --- Overlap Threshold Control ---
with st.sidebar.expander("🔎 Detection Settings", expanded=False):
    overlap_threshold = st.slider(
        "Minimum overlap (%) for text to count as inside a zone",
        min_value=0.0, max_value=1.0, value=0.8, step=0.01, format="%.4f"
    )

# --- Text Zones ---
text_zone_file = "text_zones.json"
if "text_zones" not in st.session_state:
    st.session_state.text_zones = load_json(text_zone_file, [])

with st.sidebar.expander("📐 Define Text Zones", expanded=False):
    st.markdown("### Define Copy Zone")
    zone_name = st.text_input("Text Zone Name", value="Zone 1")

    tz_x = st.number_input("Text Zone X", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.4f")
    tz_y = st.number_input("Text Zone Y", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.4f")
    tz_w = st.number_input("Text Zone W", min_value=0.0, max_value=1.0, value=0.3, step=0.01, format="%.4f")
    tz_h = st.number_input("Text Zone H", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.4f")

    if st.button("💾 Save Text Zone"):
        zones_list = load_json(text_zone_file, [])
        zones_list.append({
            "name": zone_name,
            "zone": (
                round(tz_x, 4),
                round(tz_y, 4),
                round(tz_w, 4),
                round(tz_h, 4)
            )
        })

        save_json(text_zone_file, zones_list)
        st.success(f"✅ Text zone '{zone_name}' saved!")

    zones_list = load_json(text_zone_file, [])
    if zones_list:
        st.markdown("**Saved Text Zones:**")
        for i, item in enumerate(zones_list):
            if isinstance(item, dict):  # new format
                name = item.get("name", f"Zone {i + 1}")
                zx, zy, zw, zh = item.get("zone", (0, 0, 0, 0))
            else:  # old format
                name = f"Zone {i + 1}"
                zx, zy, zw, zh = item

            st.write(f"{i + 1}: **{name}** → (x={zx:.4f}, y={zy:.4f}, w={zw:.4f}, h={zh:.4f})")

            if st.button(f"❌ Delete '{name}'", key=f"del_text_zone_{i}_{name}"):
                zones_list.pop(i)
                save_json(text_zone_file, zones_list)
                st.rerun()

# --- Ignore Settings ---
with st.sidebar.expander("🛑 Ignore Settings", expanded=False):
    if "persistent_ignore_terms" not in st.session_state:
        st.session_state["persistent_ignore_terms"] = load_ignore_terms()

    ignore_input = st.text_area("Enter words/phrases to ignore (comma separated):")
    if st.button("Apply Ignore Terms"):
        new_terms = [t.strip().lower() for t in ignore_input.split(",") if t.strip()]
        st.session_state["persistent_ignore_terms"].extend(new_terms)
        st.session_state["persistent_ignore_terms"] = sorted(set(st.session_state["persistent_ignore_terms"]))
        save_ignore_terms(st.session_state["persistent_ignore_terms"])
        st.rerun()

    if st.session_state["persistent_ignore_terms"]:
        st.markdown("**Ignored Texts:**")
        for term in st.session_state["persistent_ignore_terms"]:
            st.write(f"- {term}")

    st.markdown("### Define Ignore Zone")
    zone_name = st.text_input("Ignore Zone Name", value="Zone 1")

    iz_x = st.number_input("Ignore Zone X", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.4f")
    iz_y = st.number_input("Ignore Zone Y", min_value=0.0, max_value=1.0, value=0.9, step=0.01, format="%.4f")
    iz_w = st.number_input("Ignore Zone W", min_value=0.0, max_value=1.0, value=0.8, step=0.01, format="%.4f")
    iz_h = st.number_input("Ignore Zone H", min_value=0.0, max_value=1.0, value=0.1, step=0.01, format="%.4f")

    if st.button("Save Ignore Zone"):
        zones_list = load_ignore_zones()
        zones_list.append({
            "name": zone_name,
            "zone": (
                round(iz_x, 4),
                round(iz_y, 4),
                round(iz_w, 4),
                round(iz_h, 4)
            )
        })

        save_ignore_zones(zones_list)
        st.success(f"✅ Ignore zone '{zone_name}' saved!")
        st.rerun()

    zones_list = load_ignore_zones()
    if zones_list:
        st.markdown("**Saved Ignore Zones:**")
        for i, item in enumerate(zones_list):
            if isinstance(item, dict):
                name = item.get("name", f"Zone {i + 1}")
                zx, zy, zw, zh = item.get("zone", (0, 0, 0, 0))
            else:
                name = f"Zone {i + 1}"
                zx, zy, zw, zh = item

            st.write(f"{i + 1}: **{name}** → (x={zx:.4f}, y={zy:.4f}, w={zw:.4f}, h={zh:.4f})")

            if st.button(f"❌ Delete '{name}'", key=f"del_ignore_zone_{i}_{name}"):
                zones_list.pop(i)
                save_ignore_zones(zones_list)
                st.rerun()

# --- Image Handling ---
if uploaded_file:
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    aspect_ratio = w / h
    if abs(aspect_ratio - (8 / 3)) > 0.01:
        st.warning(f"⚠️ Image aspect ratio {w}:{h} ({aspect_ratio:.2f}) is not 8:3.")
    else:
        st.info("✅ Image aspect ratio is 8:3.")

    draw = ImageDraw.Draw(img)

    # Draw saved ignore zones (blue)
    abs_ignore_zones = []
    for item in load_ignore_zones():
        if isinstance(item, dict):
            name, (nx, ny, nw, nh) = item["name"], item["zone"]
        else:
            name, (nx, ny, nw, nh) = "Unnamed Zone", item

        ix, iy, iw, ih = int(nx * w), int(ny * h), int(nw * w), int(nh * h)
        abs_ignore_zones.append((ix, iy, iw, ih))
        draw.rectangle([ix, iy, ix + iw, iy + ih], outline="blue", width=3)
        draw.text((ix + 5, iy + 5), name, fill="blue")

    # Draw saved text zones (green)
    for item in load_json(text_zone_file, []):
        if isinstance(item, dict):
            name, (nx, ny, nw, nh) = item["name"], item["zone"]
        else:
            name, (nx, ny, nw, nh) = "Unnamed Zone", item

        zx, zy, zw, zh = int(nx * w), int(ny * h), int(nw * w), int(nh * h)
        draw.rectangle([zx, zy, zx + zw, zy + zh], outline="green", width=3)

    # OCR Detection
    results = reader.readtext(
        np.array(img),
        contrast_ths=0.05,
        adjust_contrast=0.7,
        text_threshold=0.7,
        decoder="beamsearch"
    )

    penalties = []
    score = 100
    used_zones = {item["name"]: False for item in st.session_state.text_zones}


    def overlap_ratio(text_box, zone_box):
        tx, ty, tw, th = text_box
        zx, zy, zw, zh = zone_box
        inter_x1 = max(tx, zx)
        inter_y1 = max(ty, zy)
        inter_x2 = min(tx + tw, zx + zw)
        inter_y2 = min(ty + th, zy + zh)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        text_area = tw * th
        return inter_area / text_area if text_area > 0 else 0.0


    for (bbox, text, prob) in results:
        detected_text = text.strip()

        # Convert OCR quad to bbox
        xs = [int(p[0]) for p in bbox]
        ys = [int(p[1]) for p in bbox]
        tx, ty, tw, th = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

        # Clamp to image bounds
        tx = max(0, min(tx, w - 1))
        ty = max(0, min(ty, h - 1))
        tw = max(1, min(tw, w - tx))
        th = max(1, min(th, h - ty))

        # 1) Ignore ZONES always take precedence (blue + skip)
        in_ignore_zone = False
        for izx, izy, izw, izh in abs_ignore_zones:
            if tx >= izx and ty >= izy and (tx + tw) <= (izx + izw) and (ty + th) <= (izy + izh):
                draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=3)
                in_ignore_zone = True
                break
        if in_ignore_zone:
            continue

        # 2) Check overlap with COPY ZONES
        inside_any = False
        best_ratio = 0.0
        best_zone = None

        for item in st.session_state.text_zones:
            zone_name, (nx, ny, nw, nh) = item["name"], item["zone"]
            # normalized -> absolute
            zx, zy, zw, zh = int(nx * w), int(ny * h), int(nw * w), int(nh * h)

            ratio = overlap_ratio((tx, ty, tw, th), (zx, zy, zw, zh))
            if ratio > best_ratio:
                best_ratio = ratio
                best_zone = zone_name
            if ratio >= overlap_threshold:
                inside_any = True
                used_zones[zone_name] = True
                break

        # 3) Check ignore TERMS first (regardless of zone)
        if any(term in detected_text.lower() for term in st.session_state["persistent_ignore_terms"]):
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="blue", width=2)
            continue

        # 4) If inside a copy zone (and not ignored), mark green
        if inside_any:
            draw.rectangle([tx, ty, tx + tw, ty + th], outline="green", width=2)
            continue

        # 5) Otherwise it's an infraction (red)
        draw.rectangle([tx, ty, tx + tw, ty + th], outline="red", width=2)
        if best_ratio > 0:
            msg = f"Text outside allowed zones (best overlap {best_ratio * 100:.1f}% with {best_zone})"
        else:
            msg = "Text outside allowed zones"
        penalties.append((msg, detected_text, -5))
        score -= 5


    st.image(img, caption=f"QA Result – Score: {score}", use_container_width=True)

    if penalties:
        st.error("Infractions:")
        for pen in penalties:
            if len(pen) == 3:
                msg, txt, pts = pen
                st.write(f"{msg}: '{txt}' ({pts})")
            else:
                msg, pts = pen
                st.write(f"{msg} ({pts})")
    else:
        st.success("Perfect score! ✅ All text inside zones.")
