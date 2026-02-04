#!/usr/bin/env python3
import argparse
import csv
import os
import re
from typing import Iterable, List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


VIDEO_URL_PREFIX = "https://www.youtube.com/watch?v="


def get_api_key() -> str:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Не найден ключ API. Добавьте его в переменную окружения "
            "YOUTUBE_API_KEY и запустите снова."
        )
    return api_key


def build_youtube_client():
    api_key = get_api_key()
    return build("youtube", "v3", developerKey=api_key)


def parse_keywords(raw: str) -> List[str]:
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]


def keyword_match(text: str, keywords: List[str]) -> bool:
    text_lc = text.lower()
    return any(kw in text_lc for kw in keywords)


def extract_video_id(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    match = re.search(r"v=([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)
    match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)
    return ""


def read_video_ids_from_file(path: str) -> List[str]:
    ids = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            vid = extract_video_id(line)
            if vid:
                ids.append(vid)
    return ids


def fetch_videos_details(youtube, video_ids: List[str]) -> List[Dict[str, Any]]:
    results = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = (
            youtube.videos()
            .list(part="snippet,statistics,contentDetails", id=",".join(chunk))
            .execute()
        )
        results.extend(response.get("items", []))
    return results


def search_videos(
    youtube,
    keywords: List[str],
    max_results: int,
) -> List[Dict[str, Any]]:
    found_video_ids = []
    next_page_token = None
    remaining = None if max_results <= 0 else max_results

    while True:
        response = (
            youtube.search()
            .list(
                part="snippet",
                q=" ".join(keywords),
                type="video",
                maxResults=50 if remaining is None else min(50, remaining),
                pageToken=next_page_token or "",
            )
            .execute()
        )
        for item in response.get("items", []):
            found_video_ids.append(item["id"]["videoId"])
        next_page_token = response.get("nextPageToken")
        if remaining is not None:
            remaining -= len(response.get("items", []))
            if remaining <= 0:
                break
        if not next_page_token:
            break

    videos = fetch_videos_details(youtube, found_video_ids)
    filtered = []
    for video in videos:
        snippet = video.get("snippet", {})
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        if keyword_match(title, keywords) or keyword_match(description, keywords):
            filtered.append(video)
    filtered.sort(
        key=lambda video: int(video.get("statistics", {}).get("viewCount", 0)),
        reverse=True,
    )
    return filtered


def export_search_results(videos: List[Dict[str, Any]], output_path: str) -> None:
    fieldnames = [
        "video_id",
        "url",
        "title",
        "published_at",
        "channel_title",
        "view_count",
        "like_count",
        "comment_count",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for video in videos:
            snippet = video.get("snippet", {})
            stats = video.get("statistics", {})
            video_id = video.get("id", "")
            writer.writerow(
                {
                    "video_id": video_id,
                    "url": f"{VIDEO_URL_PREFIX}{video_id}",
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "view_count": stats.get("viewCount", "0"),
                    "like_count": stats.get("likeCount", "0"),
                    "comment_count": stats.get("commentCount", "0"),
                }
            )


def fetch_top_comments(
    youtube,
    video_id: str,
    video_title: str,
    top_n: int,
) -> List[Dict[str, Any]]:
    comments = []
    next_page_token = None

    while len(comments) < top_n:
        response = (
            youtube.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, top_n - len(comments)),
                order="relevance",
                pageToken=next_page_token or "",
            )
            .execute()
        )
        items = response.get("items", [])
        if not items:
            break
        for item in items:
            snippet = item["snippet"]
            top_comment = snippet["topLevelComment"]["snippet"]
            comments.append(
                {
                    "comment_id": item["id"],
                    "video_id": video_id,
                    "video_url": f"{VIDEO_URL_PREFIX}{video_id}",
                    "video_title": video_title,
                    "author": top_comment.get("authorDisplayName", ""),
                    "text": top_comment.get("textOriginal", ""),
                    "published_at": top_comment.get("publishedAt", ""),
                    "like_count": top_comment.get("likeCount", 0),
                    "reply_count": snippet.get("totalReplyCount", 0),
                }
            )
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    for comment in comments:
        comment["score"] = int(comment["like_count"]) + int(comment["reply_count"])

    comments.sort(key=lambda c: c["score"], reverse=True)
    return comments[:top_n]


def export_comments(comments: List[Dict[str, Any]], output_path: str) -> None:
    fieldnames = [
        "comment_id",
        "video_id",
        "video_url",
        "video_title",
        "author",
        "text",
        "published_at",
        "like_count",
        "reply_count",
        "score",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for comment in comments:
            writer.writerow(comment)


def run_search(args: argparse.Namespace) -> None:
    keywords = parse_keywords(args.keywords)
    if not keywords:
        raise SystemExit("Укажите ключевые слова через запятую.")
    youtube = build_youtube_client()
    try:
        videos = search_videos(youtube, keywords, args.max_results)
    except HttpError as exc:
        raise SystemExit(f"Ошибка API: {exc}") from exc
    export_search_results(videos, args.output)
    print(f"Готово. Найдено видео: {len(videos)}. Файл: {args.output}")


def run_comments(args: argparse.Namespace) -> None:
    if not os.path.exists(args.input):
        raise SystemExit(f"Не найден файл: {args.input}")
    video_ids = read_video_ids_from_file(args.input)
    if not video_ids:
        raise SystemExit("Не удалось найти ID видео в файле.")

    youtube = build_youtube_client()
    all_comments = []
    try:
        video_items = fetch_videos_details(youtube, video_ids)
        video_titles = {
            item.get("id", ""): item.get("snippet", {}).get("title", "")
            for item in video_items
        }
        for video_id in video_ids:
            all_comments.extend(
                fetch_top_comments(
                    youtube,
                    video_id,
                    video_titles.get(video_id, ""),
                    args.top_n,
                )
            )
    except HttpError as exc:
        raise SystemExit(f"Ошибка API: {exc}") from exc

    export_comments(all_comments, args.output)
    print(f"Готово. Комментариев: {len(all_comments)}. Файл: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Парсер YouTube: поиск видео и выгрузка комментариев."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Поиск видео")
    search_parser.add_argument(
        "--keywords",
        required=True,
        help="Ключевые слова через запятую",
    )
    search_parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Максимум видео для поиска (0 = все доступные)",
    )
    search_parser.add_argument(
        "--output",
        default="search_results.csv",
        help="Путь к CSV файлу с результатом",
    )
    search_parser.set_defaults(func=run_search)

    comments_parser = subparsers.add_parser("comments", help="Выгрузка комментариев")
    comments_parser.add_argument(
        "--input",
        required=True,
        help="Файл со ссылками или ID видео (по одной строке)",
    )
    comments_parser.add_argument(
        "--top-n",
        type=int,
        default=300,
        help="Сколько топ-комментариев брать с каждого видео",
    )
    comments_parser.add_argument(
        "--output",
        default="comments.csv",
        help="Путь к CSV файлу с комментариями",
    )
    comments_parser.set_defaults(func=run_comments)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

