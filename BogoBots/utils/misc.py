import requests
import streamlit as st
from urllib.parse import quote


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
                if pic_url:
                    pic_url = pic_url.replace('/s/', '/m/')
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

def get_image_bytes_from_url(url):
    # print(f'Fetching image bytes from URL... {url}', flush=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.content
    else:
        print(f'Failed to fetch image. Status code: {response.status_code}', flush=True)
        return None
