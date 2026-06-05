"use client";

import { useState, useEffect } from "react";
import { Playlist, PlaylistVideo, API_BASE } from "@/lib/types";
import { X, Plus } from "lucide-react";

interface PlaylistModalProps {
  isOpen: boolean;
  channel: string;
  onClose: () => void;
}

export default function PlaylistModal({ isOpen, channel, onClose }: PlaylistModalProps) {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [videos, setVideos] = useState<PlaylistVideo[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");

  useEffect(() => {
    if (isOpen && channel) {
      fetchPlaylists();
    }
  }, [isOpen, channel]);

  const fetchPlaylists = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/playlists?channel=${encodeURIComponent(channel)}`);
      if (res.ok) {
        const data = await res.json();
        setPlaylists(data);
        setSelectedId(null);
        setVideos([]);
      }
    } catch (err) {
      console.error("Failed to fetch playlists:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlaylist = async (id: string) => {
    setSelectedId(id);
    try {
      const res = await fetch(`${API_BASE}/api/playlists/${id}/videos`);
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
      }
    } catch (err) {
      console.error("Failed to fetch videos:", err);
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full max-h-[85vh] overflow-y-auto">
        <div className="flex justify-between items-center p-6 border-b sticky top-0 bg-white">
          <h2 className="text-lg font-semibold">{channel} 플레이리스트</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* 새 플레이리스트 버튼 */}
          <button
            onClick={() => setShowNewForm(!showNewForm)}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />새 플레이리스트
          </button>

          {/* 새 플레이리스트 폼 */}
          {showNewForm && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded space-y-2">
              <input
                type="text"
                placeholder="플레이리스트 이름"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded"
              />
              <textarea
                placeholder="설명 (선택)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded h-20"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreatePlaylist}
                  className="flex-1 px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                >
                  만들기
                </button>
                <button
                  onClick={() => setShowNewForm(false)}
                  className="flex-1 px-3 py-2 text-sm bg-gray-400 text-white rounded hover:bg-gray-500"
                >
                  취소
                </button>
              </div>
            </div>
          )}

          {/* 플레이리스트 목록 */}
          <div className="space-y-2">
            <h3 className="font-semibold text-sm">플레이리스트 ({playlists.length})</h3>
            {loading ? (
              <div className="text-gray-500 text-sm text-center py-4">로딩 중...</div>
            ) : playlists.length === 0 ? (
              <div className="text-gray-500 text-sm text-center py-4">플레이리스트가 없습니다</div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {playlists.map((pl) => (
                  <button
                    key={pl.id}
                    onClick={() => handleSelectPlaylist(pl.id)}
                    className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                      selectedId === pl.id
                        ? "bg-blue-100 text-blue-900 border border-blue-300"
                        : "bg-gray-100 text-gray-900 hover:bg-gray-200"
                    }`}
                  >
                    <div className="font-medium">{pl.title}</div>
                    <div className="text-xs text-gray-600">{pl.item_count}개 영상</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 선택된 플레이리스트의 영상 목록 */}
          {selectedId && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm">포함된 영상 ({videos.length})</h3>
              {videos.length === 0 ? (
                <div className="text-gray-500 text-sm text-center py-4">영상이 없습니다</div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {videos.map((video) => (
                    <div
                      key={video.id}
                      className="p-2 bg-gray-50 border border-gray-200 rounded text-sm"
                    >
                      <div className="font-medium truncate">{video.title}</div>
                      <div className="text-xs text-gray-600">위치: {video.position}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
