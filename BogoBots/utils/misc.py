import requests
import streamlit as st
import os
import re
from urllib.parse import quote
import unicodedata


IMAGE_CACHE_BASE = 'static/image_cache'

def get_book_cover_from_douban(title):
    encoded_title = quote(title)
    url = f"https://book.douban.com/j/subject_suggest?q={encoded_title}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    print(f'Getting book cover from Douban... {url}', flush=True)
    response = requests.get(url, headers=headers)
    print(response.text, response.status_code, flush=True)
    if response.status_code == 200:
        try:
            results = response.json()
            print(results, flush=True)
            if results:
                pic_url = results[0].get('pic')
                # if pic_url:
                #     pic_url = pic_url.replace('/s/', '/m/')
                return pic_url
        except Exception as e:
            print(e, flush=True)
            return None
    return None

def upload_image_to_imgur(file, title, description):
    print('Uploading image to Imgur...')
    url = "https://api.imgur.com/3/image"
    headers = {
        "Authorization": f"Client-ID {st.secrets['imgur']['client_id']}"
    }
    data = {
        "image": file,
        "type": "file",
        "title": title,
        "description": description
    }
    response = requests.post(url, headers=headers, files=data)
    if response.status_code == 200:
        try:
            result = response.json()
            print(result, flush=True)
            return result['data']['link']
        except Exception as e:
            print(e, flush=True)
            return None
    return None

def get_image_from_url(url):
    # Check if image is already in cache
    cache_path = parse_url_to_cache_path(url)
    if os.path.exists(cache_path):
        # print(f'Image found in cache: {cache_path}', flush=True)
        return cache_path
    print(f'Fetching image bytes from URL... {url}', flush=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        image_bytes = response.content
        # Write image bytes to cache
        cache_path = parse_url_to_cache_path(url)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(image_bytes)
        print(f'Image cached at: {cache_path}', flush=True)
        return cache_path
    else:
        print(f'Failed to fetch image. Status code: {response.status_code}', flush=True)
        return None
    
def parse_url_to_cache_path(url):
    # Remove the protocol (http://, https://, etc.)
    url = re.sub(r'^https?://', '', url)
    
    # Replace special characters with underscores
    url = re.sub(r'[^\w\-_\. ]', '_', url)
    
    # Remove any non-ASCII characters
    url = unicodedata.normalize('NFKD', url).encode('ASCII', 'ignore').decode('ASCII')
    
    # Truncate to a reasonable length (e.g., 255 characters)
    max_length = 255
    if len(url) > max_length:
        url = url[:max_length]
        
    cache_path = os.path.join(IMAGE_CACHE_BASE, url)
    
    return cache_path
    
