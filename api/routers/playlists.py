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
    """YouTube courses URL에서 플레이리스트 자동 임포트
    
    Body: {
        "url": "https://www.youtube.com/@channel/courses",
        "channel": "채널 이름"
    }
    """
    url = req.get("url")
    channel = req.get("channel")
    
    if not url or not channel:
        raise HTTPException(status_code=400, detail="url and channel required")
    
    try:
        # yt-dlp로 플레이리스트 정보 추출
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--print", "%(playlist_id)s|%(playlist_title)s|%(id)s|%(title)s|%(thumbnail)s",
            url,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"yt-dlp error: {result.stderr}")
        
        # 출력 파싱: playlist_id|playlist_title|video_id|video_title|thumbnail
        lines = result.stdout.strip().split("\n")
        
        # 플레이리스트별로 그룹화
        playlists_dict = {}
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.split("|")
            if len(parts) < 5:
                continue
            
            playlist_id, playlist_title, video_id, video_title, thumbnail = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            if not playlist_id or not video_id:
                continue
            
            if playlist_id not in playlists_dict:
                playlists_dict[playlist_id] = {
                    "title": playlist_title,
                    "videos": [],
                }
            
            playlists_dict[playlist_id]["videos"].append({
                "id": video_id,
                "title": video_title,
                "thumbnail": thumbnail,
            })
        
        # DB에 플레이리스트 및 영상 저장
        created_count = 0
        for yt_playlist_id, playlist_data in playlists_dict.items():
            db_playlist_id = str(uuid.uuid4())
            
            # 플레이리스트 정보 저장 (ID 충돌 방지)
            existing = query_one(
                "SELECT id FROM stt_analysis.playlists WHERE youtube_playlist_id = %s AND channel = %s",
                (yt_playlist_id, channel),
            )
            
            if existing:
                db_playlist_id = existing["id"]
            else:
                execute(
                    "INSERT INTO stt_analysis.playlists (id, title, description, channel, youtube_playlist_id, item_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        db_playlist_id,
                        playlist_data["title"],
                        "",
                        channel,
                        yt_playlist_id,
                        len(playlist_data["videos"]),
                    ),
                )
                created_count += 1
            
            # 영상별 데이터 저장 및 플레이리스트 연결
            position = 1
            for video_data in playlist_data["videos"]:
                video_id = video_data["id"]
                
                # 영상이 DB에 있는지 확인
                video = query_one(
                    "SELECT id FROM stt_analysis.videos WHERE id = %s",
                    (video_id,),
                )
                
                if video:
                    # video_playlists에 이미 있는지 확인
                    existing_link = query_one(
                        "SELECT video_id FROM stt_analysis.video_playlists WHERE video_id = %s AND playlist_id = %s",
                        (video_id, db_playlist_id),
                    )
                    
                    if not existing_link:
                        execute(
                            "INSERT INTO stt_analysis.video_playlists (video_id, playlist_id, position) VALUES (%s, %s, %s)",
                            (video_id, db_playlist_id, position),
                        )
                    position += 1
        
        return {
            "ok": True,
            "playlists_created": created_count,
            "playlists_total": len(playlists_dict),
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="yt-dlp timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"import failed: {str(e)}")
