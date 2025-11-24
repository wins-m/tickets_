import feedparser
import requests
from pathlib import Path
import os
from datetime import datetime
import re
from bs4 import BeautifulSoup


RSS_URL = os.getenv("DOUBAN_RSS_URL")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
CONTENT_DIR = "content/tickets"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def extract_year_from_douban(douban_url):
    """通过豆瓣页面提取年份信息"""
    try:
        response = requests.get(douban_url, headers=HEADERS)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 方法2：从标题后的年份提取
        title_wrapper = soup.find('h1')
        if title_wrapper:
            year_match = re.search(r'\((\d{4})\)', title_wrapper.text)
            if year_match:
                return year_match.group(1)

        # 方法1：从"首播日期"提取
        year_span = soup.find('span', class_='pl',
                              string=re.compile(r'首播|上映日期'))
        if year_span:
            date_text = year_span.next_sibling.strip()
            year = re.search(r'\d{4}', date_text).group(0)
            return year

        return ""
    except Exception as e:
        print(f"Error fetching year from {douban_url}: {str(e)}")
        return ""


def get_imdb_id(douban_url):
    """从豆瓣页面提取IMDb ID（整合版）"""
    try:
        response = requests.get(douban_url, headers=HEADERS)
        return get_imdb_id_from_html(response.text)
    except Exception as e:
        print(f"获取IMDb ID失败: {str(e)}")
    return ""


def get_imdb_id_from_html(html_content):
    """
    从豆瓣HTML中提取IMDb编号
    示例输入: 包含<div id="info">...</div>的HTML文本
    返回: IMDb编号(如"tt0330904") 或空字符串
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    info_div = soup.find('div', id='info')

    if not info_div:
        return ""

    # 方法1：直接匹配IMDb标签（最可靠）
    for span in info_div.find_all('span', class_='pl'):
        if span.text == 'IMDb:':
            next_sibling = span.next_sibling
            if next_sibling:
                imdb_text = next_sibling.strip()
                if imdb_text.startswith('tt') and len(imdb_text) >= 7:
                    return imdb_text
            break

    # 方法2：备用方案 - 正则匹配整个info区域
    imdb_match = re.search(
        r'<span class="pl">IMDb:</span>\s*(tt\d{7,8})', str(info_div))
    if imdb_match:
        return imdb_match.group(1)

    return ""


def get_rating_from_omdb(imdb_id):
    """通过OMDb API获取分级信息"""
    if not imdb_id:
        return ""

    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
    try:
        data = requests.get(url).json()
        rating = data.get("Rated", "")
        if rating and (rating != 'N/A'):  # 返回如"PG-13"、"TV-MA"等
            return rating
    except Exception as e:
        print(f"OMDb API error: {str(e)}")
    return ""


def get_rating_from_tmdb(id, type="imdb_id", regions=["US", "JP", "CN", "HK", "TW", "FR", "GB", "DE", "IT", "ES", "CZ", "KR"]):
    """通过IMDB ID查询TMDB分级"""
    url = f"https://api.themoviedb.org/3/find/{id}?external_source={type}&api_key={TMDB_API_KEY}"
    try:
        data = requests.get(url).json()
    except Exception as e:
        print(f"TMDB API error: {str(e)}")
        return ""
    
    if data.get("movie_results"):
        movie_id = data["movie_results"][0]["id"]
        release_data = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates?api_key={TMDB_API_KEY}").json()
        # 第三步：按优先级查找分级
        region_rating = {x['iso_3166_1']: x['release_dates'][0]['certification']
                         for x in release_data['results'] if x['release_dates'][0]['certification']}
        if region_rating:
            for region in regions:
                if region in region_rating:
                    certification = region_rating[region]
                    print(f"Find {region} rating: {certification}")
                    return certification
            return region_rating.popitem()[1]  # 返回最后一个找到的分级
    
    elif data.get('tv_results'):
        tv_id = data['tv_results'][0]['id']
        release_data = requests.get(
            f"https://api.themoviedb.org/3/tv/{tv_id}/content_ratings?api_key={TMDB_API_KEY}").json()
        # 第三步：按优先级查找分级
        region_rating = {x['iso_3166_1']: x['rating']
                         for x in release_data['results'] if x['rating']}
        if region_rating:
            for region in regions:
                if region in region_rating:
                    certification = region_rating[region]
                    print(f"Find {region} rating: {certification}")
                    return certification
            return region_rating.popitem()[1]

    return ""


def extract_movie_info(entry):
    """从豆瓣RSS条目中提取标题、年份、封面等信息"""
    # 提取中文标题（示例：<title>看过摇曳露营△ 第二季</title>）
    title_cn = entry.title.replace("看过", "").strip()
    
    # 处理特殊符号 '/' ':'
    title_cn = title_cn.replace("/", ".")
    title_cn = title_cn.replace(":", ".")

    # 从描述中提取日文标题和年份（示例：ゆるキャン△ SEASON 2）
    foreign_title_match = re.search(r'title="([^"]+)"', entry.description)
    foreign_title = foreign_title_match.group(
        1).strip() if foreign_title_match else title_cn

    # 从封面URL提取高清图（替换s_ratio_poster为l_ratio_poster）
    cover_url = re.search(r'src="(.*?\.jpg)"', entry.description).group(1)
    hd_cover = cover_url.replace("s_ratio_poster", "l_ratio_poster")

    return {
        "title_foreign": foreign_title,
        "title_cn": title_cn,
        "douban_url": entry.link,
        "cover_url": hd_cover,
        "pub_date": datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
    }


def generate_markdown(movie_info):
    """生成Hugo兼容的Markdown文件"""

    douban_url = movie_info['douban_url']
    year = extract_year_from_douban(douban_url)
    imdb_id = get_imdb_id(douban_url)
    rating = get_rating_from_tmdb(imdb_id) or get_rating_from_omdb(imdb_id) 

    content = f"""---
title: "{movie_info['title_foreign']}"
year: "{year}"
date: "{movie_info['pub_date']}"
theaters: ["Jellyfin"]
remark: {'["' + rating + '"]' if rating else '[]'}
imdb_id: "{imdb_id or ''}"
cover: "{movie_info['cover_url']}"
douban_url: "{movie_info['douban_url']}"
---
"""
    return content


def main():
    Path(CONTENT_DIR).mkdir(parents=True, exist_ok=True)
    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries:
        if "看过" not in entry.title:
            continue

        movie_info = extract_movie_info(entry)
        filename = f"{CONTENT_DIR}/{movie_info['title_cn']}.{movie_info['pub_date']}.md"

        if not Path(filename).exists():
            content = generate_markdown(movie_info)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Generated: {filename}")
        else:
            print(f"Skiped: {filename}")


if __name__ == "__main__":
    main()
