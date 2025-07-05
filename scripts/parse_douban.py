import feedparser
import requests
from pathlib import Path
import os
from datetime import datetime
import re
from bs4 import BeautifulSoup


RSS_URL = os.getenv("DOUBAN_RSS_URL")
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
        year_span = soup.find('span', class_='pl', string=re.compile(r'首播|上映日期'))
        if year_span:
            date_text = year_span.next_sibling.strip()
            year = re.search(r'\d{4}', date_text).group(0)
            return year
        
        return ""
    except Exception as e:
        print(f"Error fetching year from {douban_url}: {str(e)}")
        return ""


def extract_movie_info(entry):
    """从豆瓣RSS条目中提取标题、年份、封面等信息"""
    # 提取中文标题（示例：<title>看过摇曳露营△ 第二季</title>）
    title_cn = entry.title.replace("看过", "").strip()
    
    # 从描述中提取日文标题和年份（示例：ゆるキャン△ SEASON 2）
    foreign_title_match = re.search(r'title="([^"]+)"', entry.description)
    foreign_title = foreign_title_match.group(1).strip() if foreign_title_match else title_cn
    
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
    content = f"""---
title: "{movie_info['title_foreign']}"
year: "{extract_year_from_douban(movie_info['douban_url']) or ''}"
date: "{movie_info['pub_date']}"
theaters: ["Jellyfin"]
remark: []
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
