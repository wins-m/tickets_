import os
import requests
from bs4 import BeautifulSoup
import time
from process_douban_records import process_douban_records


DOUBAN_USER_ID = os.getenv('DOUBAN_USER_ID')
DOUBAN_COOKIE = os.getenv('DOUBAN_COOKIE')
CONTENT_DIR = "content/tickets_douban"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Cookie': DOUBAN_COOKIE
}


def get_watched_movies(user_id, start=0):
    url = f'https://movie.douban.com/people/{user_id}/collect?start={start}'
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('div', class_='item')

            movies = []
            for item in items:
                title = item.find('li', class_='title').find('a').text.strip()
                link = item.find('li', class_='title').find('a')['href']
                date = item.find('span', class_='date').text.strip(
                ) if item.find('span', class_='date') else None
                rating = item.find('span', class_=lambda x: x and x.startswith('rating'))[
                    'class'][0] if item.find('span', class_=lambda x: x and x.startswith('rating')) else None

                movies.append({
                    'title': title,
                    'link': link,
                    'date': date,
                    'rating': rating.replace('rating', '') if rating else None
                })

            return movies
        else:
            print(f"请求失败，状态码：{response.status_code}")
            return []
    except Exception as e:
        print(f"发生错误：{e}")
        return []


def get_all_watched_movies(user_id):
    all_movies = []
    start = 0
    while True:
        movies = get_watched_movies(user_id, start)
        if not movies:
            break
        all_movies.extend(movies)
        start += len(movies)
        time.sleep(2)  # 礼貌性延迟，避免被封

        # 检查是否还有下一页
        next_page = f'https://movie.douban.com/people/{user_id}/collect?start={start}'
        response = requests.get(next_page, headers=headers)
        if '没有更多内容了' in response.text:
            break
        else:
            print(f"获取到{len(movies)}部电影，继续获取下一页...")

    return all_movies


if __name__ == "__main__":
    movies = get_all_watched_movies(DOUBAN_USER_ID)
    print(f"共获取{len(movies)}部电影")

    process_douban_records(movies, CONTENT_DIR)  # 处理获取的电影记录
