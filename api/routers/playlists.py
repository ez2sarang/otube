"""YouTube 플레이리스트 관리 라우터"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import uuid
import subprocess
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import query, query_one, execute

router = APIRouter(prefix="/api")


class PlaylistCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    channel: str


class PlaylistUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class PlaylistVideoAdd(BaseModel):
    video_ids: List[str]


class PlaylistResponse(BaseModel):
    id: str
    title: str
    description: str
    channel: str
    source_url: str
    thumbnail: str
    item_count: int
    youtube_playlist_id: str


class PlaylistVideoResponse(BaseModel):
    id: str
    title: str
    thumbnail: str
    position: int


@router.get("/playlists")
async def get_playlists(channel: Optional[str] = Query(None)):
    """채널별 플레이리스트 목록 조회"""
    if channel:
        rows = query(
            "SELECT id, title, description, channel, source_url, thumbnail, item_count, youtube_playlist_id "
            "FROM stt_analysis.playlists WHERE channel = %s ORDER BY created_at DESC",
            (channel,),
        )
    else:
        rows = query(
            "SELECT id, title, description, channel, source_url, thumbnail, item_count, youtube_playlist_id "
            "FROM stt_analysis.playlists ORDER BY created_at DESC"
        )
    
    return [
        PlaylistResponse(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            channel=row["channel"],
            source_url=row["source_url"] or "",
            thumbnail=row["thumbnail"] or "",
            item_count=row["item_count"],
            youtube_playlist_id=row["youtube_playlist_id"] or "",
        )
        for row in rows
    ]


@router.post("/playlists")
async def create_playlist(req: PlaylistCreate):
    """수동 플레이리스트 생성"""
    playlist_id = str(uuid.uuid4())
    
    execute(
        "INSERT INTO stt_analysis.playlists (id, title, description, channel) VALUES (%s, %s, %s, %s)",
        (playlist_id, req.title, req.description or "", req.channel),
    )
    
    return {"id": playlist_id, "title": req.title, "description": req.description or ""}


@router.put("/playlists/{playlist_id}")
async def update_playlist(playlist_id: str, req: PlaylistUpdate):
    """플레이리스트 수정 (제목, 설명)"""
    playlist = query_one(
        "SELECT id FROM stt_analysis.playlists WHERE id = %s",
        (playlist_id,),
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="playlist not found")
    
    if req.title:
        execute(
            "UPDATE stt_analysis.playlists SET title = %s, updated_at = NOW() WHERE id = %s",
            (req.title, playlist_id),
        )
    
    if req.description is not None:
        execute(
            "UPDATE stt_analysis.playlists SET description = %s, updated_at = NOW() WHERE id = %s",
            (req.description, playlist_id),
        )
    
    return {"ok": True}


@router.delete("/playlists/{playlist_id}")
async def delete_playlist(playlist_id: str):
    """플레이리스트 삭제 (연결된 영상은 유지)"""
    playlist = query_one(
        "SELECT id FROM stt_analysis.playlists WHERE id = %s",
        (playlist_id,),
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="playlist not found")
    
    # video_playlists 먼저 삭제
    execute(
        "DELETE FROM stt_analysis.video_playlists WHERE playlist_id = %s",
        (playlist_id,),
    )
    
    # 플레이리스트 삭제
    execute(
        "DELETE FROM stt_analysis.playlists WHERE id = %s",
        (playlist_id,),
    )
    
    return {"ok": True}


@router.get("/playlists/{playlist_id}/videos")
async def get_playlist_videos(playlist_id: str):
    """플레이리스트 내 영상 목록"""
    playlist = query_one(
        "SELECT id FROM stt_analysis.playlists WHERE id = %s",
        (playlist_id,),
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="playlist not found")
    
    rows = query(
        """
        SELECT v.id, v.title, v.thumbnail, vp.position
        FROM stt_analysis.video_playlists vp
        JOIN stt_analysis.videos v ON v.id = vp.video_id
        WHERE vp.playlist_id = %s
        ORDER BY vp.position ASC
        """,
        (playlist_id,),
    )
    
    return [
        PlaylistVideoResponse(
            id=row["id"],
            title=row["title"],
            thumbnail=row["thumbnail"] or "",
            position=row["position"],
        )
        for row in rows
    ]


@router.post("/playlists/{playlist_id}/videos")
async def add_videos_to_playlist(playlist_id: str, req: PlaylistVideoAdd):
    """플레이리스트에 영상 추가"""
    playlist = query_one(
        "SELECT id FROM stt_analysis.playlists WHERE id = %s",
        (playlist_id,),
    )
    if not playlist:
        raise HTTPException(status_code=404, detail="playlist not found")
    
    # 기존 position 확인
    max_pos = query_one(
        "SELECT MAX(position) as max_pos FROM stt_analysis.video_playlists WHERE playlist_id = %s",
        (playlist_id,),
    )
    position = (max_pos["max_pos"] or 0) + 1 if max_pos and max_pos["max_pos"] else 1
    
    # 각 비디오 추가
    for video_id in req.video_ids:
        video = query_one(
            "SELECT id FROM stt_analysis.videos WHERE id = %s",
            (video_id,),
        )
        if not video:
            continue
        
        # 이미 존재하면 스킵
        existing = query_one(
            "SELECT video_id FROM stt_analysis.video_playlists WHERE video_id = %s AND playlist_id = %s",
            (video_id, playlist_id),
        )
        if existing:
            continue
        
        execute(
            "INSERT INTO stt_analysis.video_playlists (video_id, playlist_id, position) VALUES (%s, %s, %s)",
            (video_id, playlist_id, position),
        )
        position += 1
    
    # item_count 업데이트
    count = query_one(
        "SELECT COUNT(*) as cnt FROM stt_analysis.video_playlists WHERE playlist_id = %s",
        (playlist_id,),
    )
    execute(
        "UPDATE stt_analysis.playlists SET item_count = %s, updated_at = NOW() WHERE id = %s",
        (count["cnt"], playlist_id),
    )
    
    return {"ok": True}


@router.delete("/playlists/{playlist_id}/videos/{video_id}")
async def remove_video_from_playlist(playlist_id: str, video_id: str):
    """플레이리스트에서 영상 제거"""
    execute(
        "DELETE FROM stt_analysis.video_playlists WHERE video_id = %s AND playlist_id = %s",
        (video_id, playlist_id),
    )
    
    # item_count 업데이트
    count = query_one(
        "SELECT COUNT(*) as cnt FROM stt_analysis.video_playlists WHERE playlist_id = %s",
        (playlist_id,),
    )
    execute(
        "UPDATE stt_analysis.playlists SET item_count = %s, updated_at = NOW() WHERE id = %s",
        (count["cnt"], playlist_id),
    )
    
    return {"ok": True}


@router.post("/playlists/import-youtube")
async def import_youtube_playlists(req: dict):
    """YouTube courses/playlists URL에서 플레이리스트 자동 임포트 (2-pass)

    Body: {
        "url": "https://www.youtube.com/@channel/courses",
        "channel": "채널 이름",
        "cookie_profile": "/tmp/chrome-cdp-gdrive"  // 선택
    }
    """
    url = req.get("url", "")
    channel = req.get("channel", "")
    cookie_profile = req.get("cookie_profile", "")

    if not url or not channel:
        raise HTTPException(status_code=400, detail="url and channel required")

    def yt_cmd(extra: list) -> list:
        base = ["yt-dlp", "--flat-playlist"]
        if cookie_profile:
            base += ["--cookies-from-browser", f"chrome:{cookie_profile}"]
        else:
            base += ["--cookies-from-browser", "chrome:/tmp/chrome-cdp-gdrive"]
        return base + extra

    try:
        # Pass 1: courses/playlists 탭에서 플레이리스트 목록 추출
        # --flat-playlist 시 %(id)s = 플레이리스트ID, %(title)s = 플레이리스트명
        r1 = subprocess.run(
            yt_cmd(["--print", "%(id)s|%(title)s|%(thumbnail)s", url]),
            capture_output=True, text=True, timeout=120
        )
        playlists_raw = []
        for line in r1.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) < 2 or not parts[0].startswith("PL"):
                continue
            pl_id = parts[0]
            pl_title = parts[1]
            pl_thumb = parts[2] if len(parts) > 2 else ""
            playlists_raw.append({"id": pl_id, "title": pl_title, "thumbnail": pl_thumb})

        if not playlists_raw:
            raise HTTPException(status_code=400, detail="플레이리스트를 찾을 수 없습니다. URL을 확인하세요.")

        created_count = 0
        updated_count = 0

        for pl in playlists_raw:
            yt_pl_id = pl["id"]
            pl_title = pl["title"]
            pl_thumb = pl["thumbnail"]
            pl_url = f"https://www.youtube.com/playlist?list={yt_pl_id}"

            # DB 플레이리스트 조회 or 생성
            existing_pl = query_one(
                "SELECT id FROM stt_analysis.playlists WHERE youtube_playlist_id = %s AND channel = %s",
                (yt_pl_id, channel),
            )
            if existing_pl:
                db_pl_id = existing_pl["id"]
                updated_count += 1
            else:
                db_pl_id = str(uuid.uuid4())
                execute(
                    "INSERT INTO stt_analysis.playlists "
                    "(id, title, description, channel, source_url, thumbnail, youtube_playlist_id, item_count) "
                    "VALUES (%s, %s, '', %s, %s, %s, %s, 0)",
                    (db_pl_id, pl_title, channel, pl_url, pl_thumb, yt_pl_id),
                )
                created_count += 1

            # Pass 2: 해당 플레이리스트 내 영상 목록
            r2 = subprocess.run(
                yt_cmd(["--print", "%(id)s", pl_url]),
                capture_output=True, text=True, timeout=60
            )
            video_ids = [v.strip() for v in r2.stdout.strip().splitlines() if v.strip() and not v.startswith("PL")]

            # DB에 있는 영상만 연결 (없는 건 스킵)
            linked = 0
            for pos, vid_id in enumerate(video_ids, 1):
                exists = query_one("SELECT id FROM stt_analysis.videos WHERE id = %s", (vid_id,))
                if not exists:
                    continue
                already = query_one(
                    "SELECT video_id FROM stt_analysis.video_playlists WHERE video_id=%s AND playlist_id=%s",
                    (vid_id, db_pl_id),
                )
                if not already:
                    execute(
                        "INSERT INTO stt_analysis.video_playlists (video_id, playlist_id, position) VALUES (%s, %s, %s)",
                        (vid_id, db_pl_id, pos),
                    )
                linked += 1

            execute(
                "UPDATE stt_analysis.playlists SET item_count = %s, updated_at = NOW() WHERE id = %s",
                (linked, db_pl_id),
            )

        return {
            "ok": True,
            "playlists_created": created_count,
            "playlists_updated": updated_count,
            "playlists_total": len(playlists_raw),
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="yt-dlp timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import failed: {str(e)}")
