"use client";

import { useState, useEffect } from "react";
import { Playlist, PlaylistVideo, API_BASE } from "@/lib/types";

interface PlaylistEditorProps {
  playlistId: string;
  channel: string;
  onClose: () => void;
  onUpdated: () => void;
}

export default function PlaylistEditor({ playlistId, channel, onClose, onUpdated }: PlaylistEditorProps) {
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const [videos, setVideos] = useState<PlaylistVideo[]>([]);
  const [availableVideos, setAvailableVideos] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlaylistData();
  }, [playlistId]);

  const fetchPlaylistData = async () => {
    try {
      setLoading(true);

      // 플레이리스트 정보 조회
      const playlistRes = await fetch(`${API_BASE}/api/playlists?channel=${encodeURIComponent(channel)}`);
      if (playlistRes.ok) {
        const playlists = await playlistRes.json();
        const found = playlists.find((p: Playlist) => p.id === playlistId);
        if (found) {
          setPlaylist(found);
          setTitle(found.title);
          setDescription(found.description);
        }
      }

      // 플레이리스트 내 영상 조회
      const videosRes = await fetch(`${API_BASE}/api/playlists/${playlistId}/videos`);
      if (videosRes.ok) {
        const data = await videosRes.json();
        setVideos(data);
      }
    } catch (err) {
      console.error("Failed to fetch playlist data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePlaylist = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/playlists/${playlistId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, description }),
      });

      if (res.ok) {
        onUpdated();
      }
    } catch (err) {
      console.error("Failed to update playlist:", err);
    }
  };

  const handleRemoveVideo = async (videoId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/playlists/${playlistId}/videos/${videoId}`, {
        method: "DELETE",
      });

      if (res.ok) {
        setVideos(videos.filter((v) => v.id !== videoId));
      }
    } catch (err) {
      console.error("Failed to remove video:", err);
    }
  };

  const handleDeletePlaylist = async () => {
    if (!confirm("정말로 이 플레이리스트를 삭제하시겠습니까?")) return;

    try {
      const res = await fetch(`${API_BASE}/api/playlists/${playlistId}`, {
        method: "DELETE",
      });

      if (res.ok) {
        onUpdated();
        onClose();
      }
    } catch (err) {
      console.error("Failed to delete playlist:", err);
    }
  };

  if (loading) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">플레이리스트 편집</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          {/* 플레이리스트 정보 */}
          <div>
            <label className="block text-sm font-semibold mb-1">제목</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold mb-1">설명</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded h-20"
            />
          </div>

          <button
            onClick={handleUpdatePlaylist}
            className="w-full px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            저장
          </button>

          {/* 현재 영상 목록 */}
          <div>
            <h3 className="font-semibold text-sm mb-2">현재 영상 ({videos.length}개)</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded p-2">
              {videos.length === 0 ? (
                <div className="text-gray-500 text-sm p-2">영상 없음</div>
              ) : (
                videos.map((video) => (
                  <div key={video.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                    <div className="flex-1 truncate">
                      <div className="text-sm font-medium truncate">{video.title}</div>
                      <div className="text-xs text-gray-500">위치: {video.position}</div>
                    </div>
                    <button
                      onClick={() => handleRemoveVideo(video.id)}
                      className="ml-2 px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                    >
                      제거
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 삭제 버튼 */}
          <button
            onClick={handleDeletePlaylist}
            className="w-full px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            플레이리스트 삭제
          </button>

          <button
            onClick={onClose}
            className="w-full px-3 py-2 bg-gray-400 text-white rounded hover:bg-gray-500"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
