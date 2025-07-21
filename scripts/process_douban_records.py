import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
import os
from datetime import datetime
import time


OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")


def safe_request(url, max_retries=3, delay=1):
    """带重试和延迟的安全请求函数"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response
            else:
                print(
                    f"Attempt {attempt + 1} failed with status code {response.status_code}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {str(e)}")

        if attempt < max_retries - 1:
            time.sleep(delay)

    return None


def get_rating_from_omdb(imdb_id):
    """通过OMDb API获取分级信息"""
    if not imdb_id or not OMDB_API_KEY:
        return ""

    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    try:
        response = safe_request(url)
        if response:
            data = response.json()
            rating = data.get("Rated", "")
            if rating and (rating != 'N/A'):
                return rating
    except Exception as e:
        print(f"OMDb API error: {str(e)}")
    return ""


def get_rating_from_tmdb(id, type="imdb_id", regions=["US", "JP", "CN", "HK", "TW", "FR", "GB", "DE", "IT", "ES", "CZ", "KR"]):
    """通过IMDB ID查询TMDB分级"""
    if not id or not TMDB_API_KEY:
        return ""

    url = f"https://api.themoviedb.org/3/find/{id}?external_source={type}&api_key={TMDB_API_KEY}"
    try:
        response = safe_request(url)
        if not response:
            return ""

        data = response.json()

        if data.get("movie_results"):
            movie_id = data["movie_results"][0]["id"]
            release_data = safe_request(
                f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates?api_key={TMDB_API_KEY}")
            if not release_data:
                return ""

            release_data = release_data.json()
            region_rating = {x['iso_3166_1']: x['release_dates'][0]['certification']
                             for x in release_data['results'] if x['release_dates'][0]['certification']}
            if region_rating:
                for region in regions:
                    if region in region_rating:
                        return region_rating[region]
                return region_rating.popitem()[1]

        elif data.get('tv_results'):
            tv_id = data['tv_results'][0]['id']
            release_data = safe_request(
                f"https://api.themoviedb.org/3/tv/{tv_id}/content_ratings?api_key={TMDB_API_KEY}")
            if not release_data:
                return ""

            release_data = release_data.json()
            region_rating = {x['iso_3166_1']: x['rating']
                             for x in release_data['results'] if x['rating']}
            if region_rating:
                for region in regions:
                    if region in region_rating:
                        return region_rating[region]
                return region_rating.popitem()[1]

    except Exception as e:
        print(f"TMDB API error: {str(e)}")
    return ""


def extract_movie_details(douban_url):
    """从豆瓣电影页面提取详细信息"""
    response = safe_request(douban_url)
    if not response:
        return {}

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取原始标题和年份
        title_wrapper = soup.find('h1')
        original_title = title_wrapper.find(
            'span', property='v:itemreviewed').text
        year_match = re.search(r'\((\d{4})\)', title_wrapper.text)
        year = year_match.group(1) if year_match else ""

        # 提取封面
        cover_img = soup.find('img', rel='v:image')
        cover = cover_img['src'].replace(
            's_ratio_poster', 'l_ratio_poster') if cover_img else ""

        # 提取IMDb ID
        imdb_id = ""
        info_div = soup.find('div', id='info')
        if info_div:
            for span in info_div.find_all('span', class_='pl'):
                if span.text == 'IMDb:':
                    imdb_text = span.next_sibling.strip()
                    if imdb_text.startswith('tt') and len(imdb_text) >= 7:
                        imdb_id = imdb_text
                    break

        return {
            'original_title': original_title,
            'year': year,
            'cover': cover,
            'imdb_id': imdb_id
        }
    except Exception as e:
        print(f"Error extracting details from {douban_url}: {str(e)}")
        return {}


def generate_markdown(movie):
    """生成Markdown文件内容"""
    # 从豆瓣链接获取详细信息
    details = extract_movie_details(movie['link'])

    # 处理标题（取英文名或第一个斜杠前的中文名）
    title_parts = [part.strip() for part in movie['title'].split('/')]
    foreign_title = title_parts[1] if len(title_parts) > 1 else title_parts[0]
    foreign_title = foreign_title.replace('\n', '').strip()

    # 获取分级信息
    imdb_id = details.get('imdb_id', '')
    rating_remark = get_rating_from_tmdb(
        imdb_id) or get_rating_from_omdb(imdb_id)

    # 处理豆瓣评分
    douban_rating = movie.get('rating', '')

    # 创建Markdown内容
    content = f"""---
title: "{foreign_title}"
year: "{details.get('year', '')}"
date: "{movie['date']}"
theaters: ["Jellyfin"]
rating: "{douban_rating or ''}"
remark: {'["' + rating_remark + '"]' if rating_remark else '[]'}
imdb_id: "{imdb_id}"
cover: "{details.get('cover', '')}"
douban_url: "{movie['link']}"
---
"""
    return content


def save_movie_record(movie, content_dir):
    """保存单条电影记录到Markdown文件"""
    # 生成文件名（使用中文标题和日期）
    chinese_title = movie['title'].split(
        '/')[0].strip().replace('\n', '').replace(' ', '')
    filename = f"{content_dir}/{chinese_title}.{movie['date']}.md"

    # 如果文件已存在则跳过
    if Path(filename).exists():
        print(f"Skipped existing: {filename}")
        return

    # 生成并写入内容
    content = generate_markdown(movie)
    Path(content_dir).mkdir(parents=True, exist_ok=True)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Generated: {filename}")


def process_douban_records(records, content_dir):
    """处理豆瓣观影记录列表"""
    for movie in records:
        save_movie_record(movie, content_dir)
        time.sleep(1)  # 每条请求间隔1秒


# 示例使用
if __name__ == "__main__":
    # 示例数据（实际使用时替换为你的爬取结果）
    sample_records = [
        {
            'title': '现代启示录 / Apocalypse Now\n                             / 当代启示录',
            'link': 'https://movie.douban.com/subject/1292260/',
            'date': '2025-07-19',
            'rating': '5-t'
        },
        {
            'title': '爱丽丝城市漫游记 / Alice in den Städten\n                             / 爱丽丝漫游德国(港) / Alice in the Cities',
            'link': 'https://movie.douban.com/subject/1293306/',
            'date': '2025-07-18',
            'rating': '5-t'
        }
    ]
    content_dir = "content/tickets_test"
    process_douban_records(sample_records, content_dir)
