import streamlit as st
import requests
import os
from pathlib import Path
import time
import json
import mimetypes

# Page configuration
st.set_page_config(page_title="Reverb Cloner PRO", page_icon="🎸", layout="centered")
st.title("🎸 Reverb Cloner PRO MAX - FINAL VERSION")
st.markdown("---")

API_BASE = "https://api.reverb.com/api"

def extract_listing_id(url):
    """Extract listing ID from Reverb URL"""
    try:
        if "/item/" in url:
            part = url.split("/item/")[1]
            return part.split("-")[0]
        elif "reverb.com/item/" in url:
            part = url.split("reverb.com/item/")[1]
            return part.split("-")[0]
        else:
            return None
    except Exception as e:
        st.error(f"Error parsing URL: {e}")
        return None

def parse_listing_urls(raw_input):
    """Parse multiple listing URLs (newline/comma/space separated)"""
    if not raw_input:
        return []

    separators_normalized = raw_input.replace(",", "\n").replace(";", "\n")
    urls = []
    for line in separators_normalized.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        # Handle accidental space-separated URLs on one line
        parts = cleaned.split()
        urls.extend([p for p in parts if p.startswith("http")])

    # De-duplicate while preserving order
    unique_urls = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls

def get_listing(api_key, listing_id):
    """Fetch original listing data"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Version": "3.0",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            f"{API_BASE}/listings/{listing_id}",
            headers=headers,
            timeout=15
        )

        if response.status_code != 200:
            st.error(f"Error fetching listing: {response.status_code} - {response.text}")
            return None

        return response.json()
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def extract_make_model(listing):
    """Extract make and model correctly from listing"""
    
    # Try to get make
    make = listing.get("make")
    make_name = "Unknown"
    
    if make:
        if isinstance(make, dict):
            make_name = make.get("name", "Unknown")
            if not make_name or make_name == "Unknown":
                make_name = str(make.get("_id", "Unknown"))
        elif isinstance(make, str):
            make_name = make
        elif isinstance(make, (int, float)):
            make_name = str(make)
    
    # Try to get model
    model = listing.get("model")
    model_name = "Unknown"
    
    if model:
        if isinstance(model, dict):
            model_name = model.get("name", "Unknown")
            if not model_name or model_name == "Unknown":
                model_name = str(model.get("_id", "Unknown"))
        elif isinstance(model, str):
            model_name = model
        elif isinstance(model, (int, float)):
            model_name = str(model)
    
    return make_name, model_name

def download_images(listing):
    """Download images from original listing"""
    photos = listing.get("photos", [])
    paths = []
    
    if not photos:
        st.warning("No images found in this listing")
        return []
    
    # Create images directory
    Path("images").mkdir(exist_ok=True)
    
    # Clean old images
    for old_file in Path("images").glob("*"):
        try:
            old_file.unlink()
        except:
            pass

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, photo in enumerate(photos):
        status_text.text(f"Downloading image {i+1} of {len(photos)}")
        
        try:
            # Try different possible image URL locations
            image_url = None
            
            if "_links" in photo:
                if "full" in photo["_links"]:
                    image_url = photo["_links"]["full"]["href"]
                elif "download" in photo["_links"]:
                    image_url = photo["_links"]["download"]["href"]
                elif "original" in photo["_links"]:
                    image_url = photo["_links"]["original"]["href"]
            elif "href" in photo:
                image_url = photo["href"]
            
            if not image_url:
                # Try to find any image URL in the photo object
                for key in photo:
                    if isinstance(photo[key], str) and photo[key].startswith(('http', 'https')):
                        image_url = photo[key]
                        break
            
            if not image_url:
                st.warning(f"Could not find image URL for image {i+1}")
                continue
            
            # Download image with timeout
            img_response = requests.get(image_url, timeout=15)
            
            if img_response.status_code == 200:
                file_path = f"images/img_{i}_{int(time.time())}.jpg"
                
                with open(file_path, "wb") as f:
                    f.write(img_response.content)
                
                paths.append(file_path)
                st.write(f"✅ Downloaded image {i+1}")
            else:
                st.warning(f"Failed to download image {i+1}: HTTP {img_response.status_code}")
            
        except Exception as e:
            st.warning(f"Error downloading image {i+1}: {str(e)}")
        
        progress_bar.progress((i + 1) / len(photos))

    status_text.text("All images downloaded!")
    progress_bar.empty()
    
    return paths

def create_listing(api_key, original_listing, shipping_profile_id, price_multiplier):
    """Create new listing based on original - FINAL VERSION"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Version": "3.0",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Extract make and model correctly
    make_name, model_name = extract_make_model(original_listing)
    
    st.write(f"Extracted Make: {make_name}")
    st.write(f"Extracted Model: {model_name}")
    
    # Calculate new price
    original_price = float(original_listing["price"]["amount"])
    new_price = round(original_price * price_multiplier, 2)
    new_price_cents = int(new_price * 100)

    # Get condition UUID
    condition_uuid = None
    condition = original_listing.get("condition")
    if condition:
        if isinstance(condition, dict):
            condition_uuid = condition.get("uuid")
        elif isinstance(condition, str):
            condition_uuid = condition
    
    if not condition_uuid:
        # Default condition (Good)
        condition_uuid = "df268ad1-c462-4ba6-b6db-e007e23922ea"
    
    # Get description
    description = original_listing.get("description", "")
    if not description:
        description = f"Original listing: {original_listing.get('title', 'No title')}"
    
    # Get title
    title = original_listing.get("title", f"{make_name} {model_name}".strip())
    if not title or title == "Unknown":
        title = f"{make_name} {model_name}".strip()
    
    # Get finish if available
    finish = original_listing.get("finish", "")
    
    # Get year if available
    year = original_listing.get("year", "")
    
    # Get categories if available
    categories = original_listing.get("categories", [])
    category_uuids = []
    for cat in categories:
        if isinstance(cat, dict) and "uuid" in cat:
            category_uuids.append(cat["uuid"])
    
    # SIMPLIFIED PAYLOAD - This works!
    payload = {
        "title": title,
        "description": description,
        "price": {
            "amount": new_price,
            "amount_cents": new_price_cents,
            "currency": original_listing["price"]["currency"]
        },
        "condition": {
            "uuid": condition_uuid
        },
        "make": make_name,
        "model": model_name,
        "finish": finish,
        "year": year,
        "shipping_profile_id": int(shipping_profile_id),
        "state": "draft"
    }
    
    # Add categories if available
    if category_uuids:
        payload["category_uuids"] = category_uuids
    
    st.write("Sending payload:")
    st.json(payload)

    try:
        response = requests.post(
            f"{API_BASE}/listings",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code not in [200, 201]:
            st.error(f"Error creating listing: {response.status_code}")
            st.error(f"Response: {response.text}")
            return None

        data = response.json()
        st.write("Response from API:")
        st.json(data)

        # Extract listing ID from response
        if isinstance(data, dict):
            if "listing" in data and isinstance(data["listing"], dict):
                return data["listing"].get("id")
            elif "id" in data:
                return data["id"]
        
        return None
            
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def wait_for_listing_ready(api_key, listing_id, max_wait_seconds=120):
    """Poll listing endpoint until listing is available for photo upload."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Version": "3.0",
    }

    start = time.time()
    while time.time() - start < max_wait_seconds:
        try:
            check_response = requests.get(
                f"{API_BASE}/listings/{listing_id}",
                headers=headers,
                timeout=15,
            )
            if check_response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(5)

    return False

def upload_images(api_key, listing_id, image_paths):
    """Upload images to the listing - FINAL VERSION with multiple endpoints"""
    if not image_paths:
        st.warning("No images to upload")
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Version": "3.0",
    }

    # First, check if listing exists and is ready
    if not wait_for_listing_ready(api_key, listing_id):
        st.error("❌ Cannot access the listing. It may not be ready yet.")
        return False
    
    st.write(f"✅ Listing verified, attempting to upload {len(image_paths)} images...")
    
    # Try different endpoints that might work
    endpoints_to_try = [
        f"{API_BASE}/listings/{listing_id}/photos",
        f"{API_BASE}/my/listings/{listing_id}/photos",
        f"https://api.reverb.com/api/listings/{listing_id}/photos",
        f"https://api.reverb.com/api/my/listings/{listing_id}/photos"
    ]

    progress_bar = st.progress(0)
    status_text = st.empty()
    successful_uploads = 0
    
    st.subheader("📤 Uploading Images")
    
    for i, image_path in enumerate(image_paths):
        status_text.text(f"Uploading image {i+1} of {len(image_paths)}")
        
        try:
            if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
                st.warning(f"⚠️ Invalid image file: {image_path}")
                continue
            
            # Add delay between uploads
            if i > 0:
                time.sleep(3)
            
            uploaded = False
            
            mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"

            # Try each endpoint
            for endpoint in endpoints_to_try:
                if uploaded:
                    break
                    
                with open(image_path, "rb") as img_file:
                    files_variants = [
                        {"photo": (os.path.basename(image_path), img_file, mime_type)},
                        {"file": (os.path.basename(image_path), img_file, mime_type)},
                        {"image": (os.path.basename(image_path), img_file, mime_type)},
                    ]
                    
                    for files in files_variants:
                        try:
                            img_file.seek(0)
                            upload_response = requests.post(
                                endpoint,
                                headers=headers,
                                files=files,
                                timeout=45
                            )

                            if upload_response.status_code in [200, 201, 202, 204]:
                                successful_uploads += 1
                                st.write(f"✅ Uploaded image {i+1}")
                                uploaded = True
                                break
                        except Exception:
                            continue

                    if not uploaded:
                        st.write(f"Endpoint {endpoint} upload attempt failed for image {i+1}")
            
            if not uploaded:
                st.write(f"❌ Failed to upload image {i+1} with all endpoints")
            
        except Exception as e:
            st.warning(f"❌ Error: {str(e)}")
        
        progress_bar.progress((i + 1) / len(image_paths))
    
    status_text.text(f"Upload complete! {successful_uploads}/{len(image_paths)} images uploaded")
    progress_bar.empty()
    
    if successful_uploads == 0:
        st.warning("⚠️ Could not upload images via API.")
        st.info("📌 **Manual Upload Option:**")
        st.markdown(f"1. Your images are saved in the **'images'** folder")
        st.markdown(f"2. Go to your draft listing: [Edit Listing](https://reverb.com/item/{listing_id}/edit)")
        st.markdown(f"3. Upload the images manually through the Reverb website")
        st.markdown(f"4. Then publish the listing")
    
    return successful_uploads > 0

def publish_listing(api_key, listing_id):
    """Publish a draft listing"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Version": "3.0",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.put(
            f"{API_BASE}/listings/{listing_id}/publish",
            headers=headers,
            timeout=15
        )
        
        if response.status_code in [200, 201, 204]:
            st.write(f"✅ Listing {listing_id} published successfully")
            return True
        else:
            st.warning(f"Could not publish listing: {response.status_code}")
            st.info(f"💡 You can publish manually: https://reverb.com/item/{listing_id}/edit")
            return False
    except Exception as e:
        st.warning(f"Error publishing listing: {e}")
        return False

def cleanup_images(image_paths, keep_images=False):
    """Clean up downloaded images"""
    if keep_images:
        return
    
    for image_path in image_paths:
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass

# ===== Streamlit UI =====
with st.sidebar:
    st.header("⚙️ Settings")
    
    price_multiplier = st.slider(
        "Price Multiplier", 
        min_value=0.1, 
        max_value=2.0, 
        value=0.7,
        step=0.05,
        help="Multiply original price by this value"
    )
    
    keep_images = st.checkbox(
        "Keep images after upload",
        value=False,
        help="Keep downloaded images locally after upload"
    )
    
    auto_publish = st.checkbox(
        "Auto-publish listing",
        value=True,
        help="Automatically publish the listing after image upload"
    )
    
    st.markdown("---")
    st.markdown("### 📌 Note")
    st.markdown("If API upload fails, images are saved in the 'images' folder for manual upload.")

# Main inputs
api_key = st.text_input("🔑 API Key", type="password", help="Enter your Reverb API key")

shipping_profile_id = st.text_input("📦 Shipping Profile ID", help="Enter your Shipping Profile ID")

listing_urls_input = st.text_area(
    "🔗 Listing URL(s)",
    help="Paste one or more Reverb listing URLs (newline, comma, or space separated).",
    height=140,
)

# Clone button
if st.button("🚀 Start Cloning", type="primary", use_container_width=True):
    
    # Validate inputs
    if not api_key:
        st.error("❌ Please enter your API Key")
        st.stop()
    
    if not shipping_profile_id:
        st.error("❌ Please enter your Shipping Profile ID")
        st.stop()
    
    listing_urls = parse_listing_urls(listing_urls_input)
    if not listing_urls:
        st.error("❌ Please enter at least one valid Listing URL")
        st.stop()

    if len(listing_urls) > 200:
        st.error("❌ Please process up to 200 listings per run to avoid API throttling")
        st.stop()
    
    # Start cloning process
    with st.spinner("Processing your request..."):
        
        st.info(f"📦 Processing {len(listing_urls)} listing URL(s)")
        run_progress = st.progress(0)
        results = []

        for index, listing_url in enumerate(listing_urls, start=1):
            st.markdown("---")
            st.subheader(f"Listing {index}/{len(listing_urls)}")

            listing_id = extract_listing_id(listing_url)

            if not listing_id:
                st.error(f"❌ Invalid URL format: {listing_url}")
                results.append({"source": listing_url, "new_id": None, "status": "failed_invalid_url"})
                run_progress.progress(index / len(listing_urls))
                continue

            st.info(f"📋 Original Listing ID: {listing_id}")

            original_listing = get_listing(api_key, listing_id)
            if not original_listing:
                results.append({"source": listing_url, "new_id": None, "status": "failed_fetch"})
                run_progress.progress(index / len(listing_urls))
                continue

            st.info("📥 Downloading images...")
            image_paths = download_images(original_listing)
            st.success(f"✅ Downloaded {len(image_paths)} images")

            st.info("📝 Creating new listing...")
            new_listing_id = create_listing(api_key, original_listing, shipping_profile_id, price_multiplier)

            if not new_listing_id:
                cleanup_images(image_paths, keep_images=True)
                results.append({"source": listing_url, "new_id": None, "status": "failed_create"})
                run_progress.progress(index / len(listing_urls))
                continue

            st.success(f"✅ Created new listing with ID: {new_listing_id}")

            if image_paths:
                st.info("📤 Uploading images...")
                upload_success = upload_images(api_key, new_listing_id, image_paths)

                if upload_success:
                    st.success("✅ Images uploaded successfully")
                else:
                    st.warning("⚠️ Some images failed to upload")

            if auto_publish and new_listing_id:
                st.info("📢 Publishing listing...")
                publish_listing(api_key, new_listing_id)

            cleanup_images(image_paths, keep_images)
            results.append({"source": listing_url, "new_id": new_listing_id, "status": "success"})

            # Reduce chance of Reverb API throttling on large batches
            if index < len(listing_urls):
                time.sleep(2)

            run_progress.progress(index / len(listing_urls))

        success_count = len([r for r in results if r["status"] == "success"])
        st.balloons()
        st.success(f"🎉 Clone run completed: {success_count}/{len(listing_urls)} success")

        st.subheader("Run Summary")
        st.table(results)

        for item in results:
            if item["new_id"]:
                st.markdown(f"🔗 [View listing {item['new_id']}](https://reverb.com/item/{item['new_id']})")
                st.markdown(f"✏️ [Edit listing {item['new_id']}](https://reverb.com/item/{item['new_id']}/edit)")

# Add footer
st.markdown("---")
st.markdown("Made with 🎸 for Reverb sellers | FINAL VERSION with all fixes")
