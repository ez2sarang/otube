"use client";

import { useState, useEffect } from "react";
import { Playlist, PlaylistVideo, API_BASE } from "@/lib/types";
import PlaylistEditor from "./PlaylistEditor";

interface PlaylistPanelProps {
  channel: string;
  onPlaylistSelect: (playlistId: string | null) => void;
}

export default function PlaylistPanel({ channel, onPlaylistSelect }: PlaylistPanelProps) {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  // 플레이리스트 목록 조회
  useEffect(() => {
    if (!channel) return;
    fetchPlaylists();
  }, [channel]);

  const fetchPlaylists = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/playlists?channel=${encodeURIComponent(channel)}`);
      if (res.ok) {
        const data = await res.json();
        setPlaylists(data);
      }
    } catch (err) {
      console.error("Failed to fetch playlists:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePlaylist = async () => {
    if (!newTitle.trim()) return;

    try {
      const res = await fetch(`${API_BASE}/api/playlists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          description: newDesc,
          channel,
        }),
      });

      if (res.ok) {
        setNewTitle("");
        setNewDesc("");
        setShowNewForm(false);
        fetchPlaylists();
      }
    } catch (err) {
      console.error("Failed to create playlist:", err);
    }
  };

  const handleSelectPlaylist = (id: string | null) => {
    setSelectedId(id);
    onPlaylistSelect(id);
  };

  const handlePlaylistUpdated = () => {
    setEditingId(null);
    fetchPlaylists();
  };

  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 p-4 overflow-y-auto max-h-[calc(100vh-120px)]">
      <div className="space-y-3 mb-4">
        <button
          onClick={() => setShowNewForm(!showNewForm)}
          className="w-full px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          + 새 플레이리스트
        </button>
        <button
          onClick={() => {
            // 유튜브 임포트 로직 추후 추가
            alert("YouTube 임포트는 곧 추가됩니다");
          }}
          className="w-full px-3 py-2 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
        >
          YouTube에서 가져오기
        </button>
      </div>

      {showNewForm && (
        <div className="mb-4 p-3 bg-white border border-gray-200 rounded">
          <input
            type="text"
            placeholder="플레이리스트 이름"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="w-full px-2 py-1 text-sm border border-gray-300 rounded mb-2"
          />
          <textarea
            placeholder="설명 (선택)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full px-2 py-1 text-sm border border-gray-300 rounded mb-2 h-16"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreatePlaylist}
              className="flex-1 px-2 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              만들기
            </button>
            <button
              onClick={() => setShowNewForm(false)}
              className="flex-1 px-2 py-1 text-sm bg-gray-400 text-white rounded hover:bg-gray-500"
            >
              취소
            </button>
          </div>
        </div>
      )}

      <div className="space-y-1">
        {/* 전체 영상 */}
        <button
          onClick={() => handleSelectPlaylist(null)}
          className={`w-full text-left px-3 py-2 text-sm rounded ${
            selectedId === null ? "bg-blue-100 text-blue-900 font-semibold" : "hover:bg-gray-200"
          }`}
        >
          전체 영상
        </button>

        {/* 플레이리스트 목록 */}
        {loading ? (
          <div className="text-gray-500 text-sm px-3 py-2">로딩 중...</div>
        ) : playlists.length === 0 ? (
          <div className="text-gray-500 text-sm px-3 py-2">플레이리스트 없음</div>
        ) : (
          playlists.map((pl) => (
            <div key={pl.id} className="flex items-center gap-2">
              <button
                onClick={() => handleSelectPlaylist(pl.id)}
                className={`flex-1 text-left px-3 py-2 text-sm rounded ${
                  selectedId === pl.id ? "bg-blue-100 text-blue-900 font-semibold" : "hover:bg-gray-200"
                }`}
              >
                <div className="truncate">{pl.title}</div>
                <div className="text-xs text-gray-500">({pl.item_count}개)</div>
              </button>
              <button
                onClick={() => setEditingId(pl.id)}
                className="px-2 py-1 text-xs bg-gray-400 text-white rounded hover:bg-gray-500"
              >
                편집
              </button>
            </div>
          ))
        )}
      </div>

      {/* 플레이리스트 편집 모달 */}
      {editingId && (
        <PlaylistEditor
          playlistId={editingId}
          channel={channel}
          onClose={() => setEditingId(null)}
          onUpdated={handlePlaylistUpdated}
        />
      )}
    </div>
  );
}
