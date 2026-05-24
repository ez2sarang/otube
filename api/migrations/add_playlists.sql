-- Playlist functionality migration
-- Tracks YouTube playlists/series and video membership

CREATE TABLE IF NOT EXISTS stt_analysis.playlists (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    channel TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    thumbnail TEXT DEFAULT '',
    item_count INTEGER DEFAULT 0,
    youtube_playlist_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stt_analysis.video_playlists (
    video_id TEXT REFERENCES stt_analysis.videos(id) ON DELETE CASCADE,
    playlist_id TEXT REFERENCES stt_analysis.playlists(id) ON DELETE CASCADE,
    position INTEGER DEFAULT 0,
    PRIMARY KEY (video_id, playlist_id)
);

CREATE INDEX IF NOT EXISTS idx_video_playlists_playlist ON stt_analysis.video_playlists(playlist_id);
CREATE INDEX IF NOT EXISTS idx_video_playlists_video ON stt_analysis.video_playlists(video_id);
CREATE INDEX IF NOT EXISTS idx_playlists_channel ON stt_analysis.playlists(channel);
