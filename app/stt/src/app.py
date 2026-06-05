"""STT 웹앱 + 하네스 편집기 (Flask)"""
import json
import os
import sys
import threading
import time
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify

# 같은 디렉토리의 transcribe 모듈
sys.path.insert(0, os.path.dirname(__file__))
from transcribe import process_url, transcribe_audio, format_transcript_md, format_transcript_srt, extract_clips

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HARNESS_DIR = PROJECT_ROOT / "harness"
APP_HARNESS_DIR = PROJECT_ROOT / "app" / "stt" / "harness"

app = Flask(__name__)

# 진행 상태 저장
progress_state = {"status": "idle", "message": ""}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Offline Thinking - STT & 하네스 편집기</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; color: #333; }

.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 20px 32px; }
.header h1 { font-size: 1.5em; font-weight: 600; }
.header p { font-size: 0.9em; opacity: 0.8; margin-top: 4px; }

.tabs { display: flex; background: #fff; border-bottom: 2px solid #e2e8f0; padding: 0 32px; }
.tab { padding: 14px 24px; cursor: pointer; font-weight: 500; color: #64748b; border-bottom: 3px solid transparent; transition: all 0.2s; }
.tab:hover { color: #334155; }
.tab.active { color: #2563eb; border-bottom-color: #2563eb; }

.tab-content { display: none; padding: 24px 32px; max-width: 1200px; }
.tab-content.active { display: block; }

.card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card h3 { margin-bottom: 16px; font-size: 1.1em; color: #1e293b; }

.form-row { display: flex; gap: 12px; margin-bottom: 12px; align-items: end; }
.form-group { flex: 1; }
.form-group label { display: block; font-size: 0.85em; font-weight: 500; color: #475569; margin-bottom: 4px; }
.form-group input, .form-group select, .form-group textarea {
    width: 100%; padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px;
    font-size: 0.95em; transition: border-color 0.2s;
}
.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
    outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}
textarea { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.88em; line-height: 1.6; resize: vertical; }

.btn { padding: 10px 24px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.95em; transition: all 0.2s; }
.btn-primary { background: #2563eb; color: white; }
.btn-primary:hover { background: #1d4ed8; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-secondary { background: #e2e8f0; color: #475569; }
.btn-secondary:hover { background: #cbd5e1; }
.btn-sm { padding: 6px 14px; font-size: 0.85em; }

.status-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; font-family: monospace; font-size: 0.88em; min-height: 60px; white-space: pre-wrap; }
.status-box.running { border-color: #f59e0b; background: #fffbeb; }
.status-box.done { border-color: #10b981; background: #f0fdf4; }
.status-box.error { border-color: #ef4444; background: #fef2f2; }

.output-tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.output-tab { padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85em; background: #f1f5f9; color: #64748b; }
.output-tab.active { background: #2563eb; color: white; }

.output-area { min-height: 300px; max-height: 500px; overflow-y: auto; }
.copy-btn { float: right; font-size: 0.8em; }

/* 하네스 편집기 */
.harness-layout { display: flex; gap: 16px; }
.harness-sidebar { width: 280px; flex-shrink: 0; }
.harness-main { flex: 1; min-width: 0; }

.file-tree { background: #f8fafc; border-radius: 8px; padding: 12px; max-height: 400px; overflow-y: auto; }
.file-item { padding: 6px 10px; cursor: pointer; border-radius: 6px; font-size: 0.85em; word-break: break-all; }
.file-item:hover { background: #e2e8f0; }
.file-item.active { background: #dbeafe; color: #1d4ed8; font-weight: 500; }
.file-category { font-size: 0.75em; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 12px 0 4px 10px; }

.file-info { background: #f0f4f8; padding: 8px 14px; border-radius: 6px; font-size: 0.83em; color: #475569; margin-bottom: 12px; }

.overview-card { font-size: 0.9em; }
.overview-card table { width: 100%; border-collapse: collapse; }
.overview-card th, .overview-card td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #e2e8f0; font-size: 0.9em; }
.overview-card th { font-weight: 600; color: #64748b; }

.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #d1d5db; border-top-color: #2563eb; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 8px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }

.clip-card { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; transition: box-shadow 0.2s; }
.clip-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.clip-card img { width: 100%; height: auto; display: block; }
.clip-card .clip-info { padding: 10px 12px; }
.clip-card .clip-time { font-size: 0.8em; font-weight: 600; color: #2563eb; font-family: monospace; }
.clip-card .clip-text { font-size: 0.85em; color: #475569; margin-top: 6px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

@media (max-width: 768px) {
    .form-row { flex-direction: column; }
    .harness-layout { flex-direction: column; }
    .harness-sidebar { width: 100%; }
    .tabs { overflow-x: auto; }
}
</style>
</head>
<body>

<div class="header">
    <h1>Offline Thinking</h1>
    <p>YouTube STT 변환 & 하네스 엔지니어링 편집기</p>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab('stt')">YouTube STT</div>
    <div class="tab" onclick="switchTab('clips')">클립보드</div>
    <div class="tab" onclick="switchTab('file')">파일 STT</div>
    <div class="tab" onclick="switchTab('harness')">하네스 편집기</div>
</div>

<!-- Tab 1: YouTube STT -->
<div id="tab-stt" class="tab-content active">
    <div class="card">
        <h3>YouTube 영상을 텍스트로 변환</h3>
        <div class="form-row">
            <div class="form-group" style="flex:3">
                <label>YouTube URL</label>
                <input type="text" id="yt-url" placeholder="https://youtu.be/... 또는 https://www.youtube.com/watch?v=...">
            </div>
            <div class="form-group" style="flex:1">
                <label>언어</label>
                <select id="yt-lang">
                    <option value="ko" selected>한국어</option>
                    <option value="en">영어</option>
                    <option value="ja">일본어</option>
                    <option value="zh">중국어</option>
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group" style="flex:2">
                <label>모델</label>
                <select id="yt-model">
                    <option value="mlx-community/whisper-large-v3-turbo" selected>large-v3-turbo (권장)</option>
                    <option value="mlx-community/whisper-large-v3">large-v3 (최고 품질)</option>
                    <option value="mlx-community/whisper-small">small (가벼움)</option>
                </select>
            </div>
            <div class="form-group" style="flex:1">
                <button class="btn btn-primary" id="yt-btn" onclick="startYtTranscribe()">변환 시작</button>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>상태</h3>
        <div class="status-box" id="yt-status">대기 중...</div>
    </div>

    <div class="card">
        <h3>결과</h3>
        <div class="output-tabs">
            <div class="output-tab active" onclick="switchOutput('md')">마크다운</div>
            <div class="output-tab" onclick="switchOutput('srt')">SRT 자막</div>
            <div class="output-tab" onclick="switchOutput('raw')">원본 텍스트</div>
            <button class="btn btn-secondary btn-sm copy-btn" onclick="copyOutput()">복사</button>
        </div>
        <div class="output-area">
            <textarea id="output-md" rows="15" readonly style="width:100%"></textarea>
            <textarea id="output-srt" rows="15" readonly style="width:100%; display:none"></textarea>
            <textarea id="output-raw" rows="15" readonly style="width:100%; display:none"></textarea>
        </div>
    </div>
</div>

<!-- Tab 2: Clips -->
<div id="tab-clips" class="tab-content">
    <div class="card">
        <h3>영상 클립보드 생성</h3>
        <p style="color:#64748b;font-size:0.9em;margin-bottom:16px">영상에서 장면 전환점을 감지하고, 각 장면의 스크린샷 + STT 텍스트를 클립보드로 만듭니다.</p>
        <div class="form-row">
            <div class="form-group" style="flex:3">
                <label>YouTube URL</label>
                <input type="text" id="clip-url" placeholder="https://youtu.be/...">
            </div>
            <div class="form-group" style="flex:1">
                <label>언어</label>
                <select id="clip-lang">
                    <option value="ko" selected>한국어</option>
                    <option value="en">영어</option>
                    <option value="ja">일본어</option>
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group" style="flex:1">
                <label>캡처 간격 (초)</label>
                <input type="number" id="clip-interval" value="30" min="10" max="120">
            </div>
            <div class="form-group" style="flex:1">
                <label>최대 클립 수</label>
                <input type="number" id="clip-max" value="40" min="5" max="100">
            </div>
            <div class="form-group" style="flex:1">
                <button class="btn btn-primary" id="clip-btn" onclick="startClipExtract()">클립보드 생성</button>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>상태</h3>
        <div class="status-box" id="clip-status">대기 중...</div>
    </div>

    <div class="card" id="clip-results" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <h3 style="margin:0">클립보드</h3>
            <button class="btn btn-secondary btn-sm" onclick="copyClipsAsMarkdown()">마크다운으로 복사</button>
        </div>
        <div id="clip-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px"></div>
    </div>

    <div class="card" id="clip-md-card" style="display:none">
        <h3>마크다운 출력 <button class="btn btn-secondary btn-sm copy-btn" onclick="document.getElementById('clip-md-output').select();document.execCommand('copy');alert('복사됨!')">복사</button></h3>
        <textarea id="clip-md-output" rows="15" readonly style="width:100%"></textarea>
    </div>
</div>

<!-- Tab 3: File STT -->
<div id="tab-file" class="tab-content">
    <div class="card">
        <h3>로컬 파일 STT 변환</h3>
        <div class="form-row">
            <div class="form-group" style="flex:3">
                <label>오디오/비디오 파일</label>
                <input type="file" id="file-input" accept="audio/*,video/*,.mp3,.wav,.m4a,.mp4,.webm">
            </div>
            <div class="form-group" style="flex:1">
                <label>언어</label>
                <select id="file-lang">
                    <option value="ko" selected>한국어</option>
                    <option value="en">영어</option>
                    <option value="ja">일본어</option>
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group" style="flex:2">
                <label>모델</label>
                <select id="file-model">
                    <option value="mlx-community/whisper-large-v3-turbo" selected>large-v3-turbo (권장)</option>
                    <option value="mlx-community/whisper-large-v3">large-v3 (최고 품질)</option>
                </select>
            </div>
            <div class="form-group" style="flex:1">
                <button class="btn btn-primary" id="file-btn" onclick="startFileTranscribe()">변환 시작</button>
            </div>
        </div>
    </div>
    <div class="card">
        <h3>상태</h3>
        <div class="status-box" id="file-status">대기 중...</div>
    </div>
    <div class="card">
        <h3>결과</h3>
        <textarea id="file-output" rows="20" readonly style="width:100%"></textarea>
    </div>
</div>

<!-- Tab 3: Harness Editor -->
<div id="tab-harness" class="tab-content">
    <div class="harness-layout">
        <div class="harness-sidebar">
            <div class="card overview-card">
                <h3>하네스 4요소</h3>
                <table>
                    <tr><th>요소</th><th>상태</th></tr>
                    <tr><td>헌법</td><td id="ov-constitution">-</td></tr>
                    <tr><td>작업 구조</td><td id="ov-specs">-</td></tr>
                    <tr><td>검증</td><td id="ov-tests">-</td></tr>
                    <tr><td>실행 루프</td><td id="ov-workflows">-</td></tr>
                </table>
            </div>
            <div class="card">
                <h3>파일 목록 <button class="btn btn-secondary btn-sm" onclick="loadFileTree()" style="float:right">새로고침</button></h3>
                <div class="file-tree" id="file-tree"></div>
            </div>
        </div>

        <div class="harness-main">
            <div class="card">
                <div class="file-info" id="harness-file-info">파일을 선택해주세요.</div>
                <textarea id="harness-editor" rows="30" style="width:100%" placeholder="왼쪽에서 파일을 선택하면 내용이 여기에 표시됩니다."></textarea>
                <div class="form-row" style="margin-top:12px">
                    <button class="btn btn-primary" onclick="saveHarnessFile()">저장</button>
                    <div class="status-box" id="harness-save-status" style="flex:1; min-height:auto; padding:8px 12px;">-</div>
                </div>
            </div>

            <div class="card" style="margin-top:12px">
                <h3>새 파일 만들기</h3>
                <div class="form-row">
                    <div class="form-group" style="flex:2">
                        <label>파일 이름</label>
                        <input type="text" id="new-file-name" placeholder="my-new-rule.md">
                    </div>
                    <div class="form-group" style="flex:2">
                        <label>카테고리</label>
                        <select id="new-file-category">
                            <option value="harness/core/">레포 > 코어</option>
                            <option value="harness/roles/">레포 > 역할</option>
                            <option value="harness/workflows/">레포 > 워크플로우</option>
                            <option value="harness/templates/">레포 > 템플릿</option>
                            <option value="app/stt/harness/docs/">앱 > 문서</option>
                            <option value="app/stt/harness/specs/">앱 > 기능 명세</option>
                            <option value="app/stt/harness/plans/">앱 > 로드맵</option>
                            <option value="app/stt/harness/references/">앱 > 참고 자료</option>
                        </select>
                    </div>
                    <div class="form-group" style="flex:1">
                        <button class="btn btn-secondary" onclick="createHarnessFile()">생성</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
let currentOutput = 'md';
let currentHarnessFile = '';

function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-' + name).classList.add('active');
    if (name === 'harness') loadFileTree();
}

function switchOutput(type) {
    currentOutput = type;
    document.querySelectorAll('.output-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    ['md','srt','raw'].forEach(t => {
        document.getElementById('output-' + t).style.display = t === type ? 'block' : 'none';
    });
}

function copyOutput() {
    const el = document.getElementById('output-' + currentOutput);
    el.select();
    document.execCommand('copy');
    alert('복사되었습니다!');
}

async function startYtTranscribe() {
    const url = document.getElementById('yt-url').value.trim();
    if (!url) { alert('URL을 입력해주세요.'); return; }

    const btn = document.getElementById('yt-btn');
    const status = document.getElementById('yt-status');
    btn.disabled = true;
    btn.textContent = '변환 중...';
    status.className = 'status-box running';
    status.innerHTML = '<span class="spinner"></span>다운로드 및 STT 변환 중... (수 분 소요될 수 있습니다)';

    try {
        const resp = await fetch('/api/transcribe/youtube', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url: url,
                language: document.getElementById('yt-lang').value,
                model: document.getElementById('yt-model').value
            })
        });
        const data = await resp.json();

        if (data.error) {
            status.className = 'status-box error';
            status.textContent = '오류: ' + data.error;
        } else {
            status.className = 'status-box done';
            status.textContent = '완료! 제목: ' + data.title + '\\n세그먼트: ' + data.segments + '개 | 소요: ' + data.elapsed.toFixed(1) + '초';
            document.getElementById('output-md').value = data.markdown || '';
            document.getElementById('output-srt').value = data.srt || '';
            document.getElementById('output-raw').value = data.text || '';
        }
    } catch (e) {
        status.className = 'status-box error';
        status.textContent = '요청 실패: ' + e.message;
    }

    btn.disabled = false;
    btn.textContent = '변환 시작';
}

async function startFileTranscribe() {
    const fileInput = document.getElementById('file-input');
    if (!fileInput.files.length) { alert('파일을 선택해주세요.'); return; }

    const btn = document.getElementById('file-btn');
    const status = document.getElementById('file-status');
    btn.disabled = true;
    status.className = 'status-box running';
    status.innerHTML = '<span class="spinner"></span>업로드 및 변환 중...';

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('language', document.getElementById('file-lang').value);
    formData.append('model', document.getElementById('file-model').value);

    try {
        const resp = await fetch('/api/transcribe/file', { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.error) {
            status.className = 'status-box error';
            status.textContent = '오류: ' + data.error;
        } else {
            status.className = 'status-box done';
            status.textContent = '완료! 세그먼트: ' + data.segments + '개 | 소요: ' + data.elapsed.toFixed(1) + '초';
            document.getElementById('file-output').value = data.markdown || '';
        }
    } catch (e) {
        status.className = 'status-box error';
        status.textContent = '요청 실패: ' + e.message;
    }

    btn.disabled = false;
    btn.textContent = '변환 시작';
}

// 클립보드
let clipsData = [];

async function startClipExtract() {
    const url = document.getElementById('clip-url').value.trim();
    if (!url) { alert('URL을 입력해주세요.'); return; }

    const btn = document.getElementById('clip-btn');
    const status = document.getElementById('clip-status');
    btn.disabled = true;
    btn.textContent = '생성 중...';
    status.className = 'status-box running';
    status.innerHTML = '<span class="spinner"></span>비디오 다운로드 + STT + 프레임 추출 중... (수 분 소요)';

    try {
        const resp = await fetch('/api/clips/extract', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                url: url,
                language: document.getElementById('clip-lang').value,
                interval: parseInt(document.getElementById('clip-interval').value) || 30,
                max_clips: parseInt(document.getElementById('clip-max').value) || 40
            })
        });
        const data = await resp.json();

        if (data.error) {
            status.className = 'status-box error';
            status.textContent = '오류: ' + data.error;
        } else {
            status.className = 'status-box done';
            status.textContent = '완료! 제목: ' + data.title + '\\n장면 전환: ' + data.scene_changes + '개 | 클립: ' + data.total_clips + '개 | 소요: ' + data.elapsed.toFixed(1) + '초';

            clipsData = data.clips || [];
            renderClips(clipsData);

            document.getElementById('clip-results').style.display = 'block';
            document.getElementById('clip-md-card').style.display = 'block';
            document.getElementById('clip-md-output').value = data.markdown || '';
        }
    } catch (e) {
        status.className = 'status-box error';
        status.textContent = '요청 실패: ' + e.message;
    }

    btn.disabled = false;
    btn.textContent = '클립보드 생성';
}

function renderClips(clips) {
    const grid = document.getElementById('clip-grid');
    grid.innerHTML = clips.map(c => `
        <div class="clip-card">
            <img src="/api/clips/frame/${c.index}" alt="Frame at ${c.time_str}" loading="lazy">
            <div class="clip-info">
                <div class="clip-time">${c.time_str}</div>
                <div class="clip-text">${c.text || '(텍스트 없음)'}</div>
            </div>
        </div>
    `).join('');
}

function copyClipsAsMarkdown() {
    const el = document.getElementById('clip-md-output');
    el.select();
    document.execCommand('copy');
    alert('마크다운으로 복사되었습니다!');
}

// 하네스 편집기
async function loadFileTree() {
    const resp = await fetch('/api/harness/files');
    const data = await resp.json();

    // 개요 업데이트
    document.getElementById('ov-constitution').textContent = data.overview.constitution;
    document.getElementById('ov-specs').textContent = data.overview.specs;
    document.getElementById('ov-tests').textContent = data.overview.tests;
    document.getElementById('ov-workflows').textContent = data.overview.workflows;

    // 파일 트리 렌더
    const tree = document.getElementById('file-tree');
    let html = '';
    let lastCategory = '';

    for (const f of data.files) {
        const cat = f.split('/').slice(0, -1).join('/');
        if (cat !== lastCategory) {
            lastCategory = cat;
            html += '<div class="file-category">' + cat + '</div>';
        }
        const active = f === currentHarnessFile ? ' active' : '';
        html += '<div class="file-item' + active + '" onclick="loadHarnessFile(\\''+f+'\\')">' + f.split('/').pop() + '</div>';
    }
    tree.innerHTML = html;
}

async function loadHarnessFile(path) {
    currentHarnessFile = path;
    const resp = await fetch('/api/harness/load?path=' + encodeURIComponent(path));
    const data = await resp.json();

    document.getElementById('harness-editor').value = data.content || '';
    document.getElementById('harness-file-info').textContent = data.info || path;
    document.getElementById('harness-save-status').textContent = '-';

    // 파일 트리에서 active 표시
    document.querySelectorAll('.file-item').forEach(el => {
        el.classList.toggle('active', el.textContent === path.split('/').pop());
    });
}

async function saveHarnessFile() {
    if (!currentHarnessFile) { alert('파일을 선택해주세요.'); return; }

    const content = document.getElementById('harness-editor').value;
    const resp = await fetch('/api/harness/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ path: currentHarnessFile, content: content })
    });
    const data = await resp.json();
    const el = document.getElementById('harness-save-status');
    el.textContent = data.message || '저장 완료';
    el.style.color = data.error ? '#ef4444' : '#10b981';
}

async function createHarnessFile() {
    const name = document.getElementById('new-file-name').value.trim();
    if (!name) { alert('파일 이름을 입력해주세요.'); return; }

    const category = document.getElementById('new-file-category').value;
    const resp = await fetch('/api/harness/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name: name, category: category })
    });
    const data = await resp.json();

    if (data.error) {
        alert('오류: ' + data.error);
    } else {
        alert('생성 완료: ' + data.path);
        loadFileTree();
        loadHarnessFile(data.path);
    }
}
</script>

</body>
</html>
"""


# ─── API 라우트 ───

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/transcribe/youtube", methods=["POST"])
def api_transcribe_youtube():
    data = request.json
    url = data.get("url", "").strip()
    language = data.get("language", "ko")
    model = data.get("model", "mlx-community/whisper-large-v3-turbo")

    if not url:
        return jsonify({"error": "URL이 필요합니다."})

    try:
        result = process_url(url, language=language, model=model)
        return jsonify({
            "title": result["title"],
            "text": result["text"],
            "markdown": result["markdown"],
            "srt": result["srt"],
            "segments": result["segments"],
            "elapsed": result["elapsed"],
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/transcribe/file", methods=["POST"])
def api_transcribe_file():
    if "file" not in request.files:
        return jsonify({"error": "파일이 필요합니다."})

    file = request.files["file"]
    language = request.form.get("language", "ko")
    model = request.form.get("model", "mlx-community/whisper-large-v3-turbo")

    # 임시 저장
    import tempfile
    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        start = time.time()
        result = transcribe_audio(tmp_path, language=language, model=model)
        elapsed = time.time() - start

        md_text = format_transcript_md(result, file.filename)
        srt_text = format_transcript_srt(result)

        return jsonify({
            "markdown": md_text,
            "srt": srt_text,
            "text": result.get("text", ""),
            "segments": len(result.get("segments", [])),
            "elapsed": elapsed,
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        os.unlink(tmp_path)


# 클립 관련 상태 (세션 단순화를 위해 글로벌)
_clip_state = {"clips": [], "frames_dir": "", "title": ""}


@app.route("/api/clips/extract", methods=["POST"])
def api_clips_extract():
    data = request.json
    url = data.get("url", "").strip()
    language = data.get("language", "ko")
    interval = data.get("interval", 30)
    max_clips = data.get("max_clips", 40)

    if not url:
        return jsonify({"error": "URL이 필요합니다."})

    try:
        start_time = time.time()

        # 1. STT 먼저
        from transcribe import get_video_title, download_audio, transcribe_audio
        title = get_video_title(url)
        output_dir = "/tmp/stt-work"
        audio_path = download_audio(url, output_dir)
        stt_result = transcribe_audio(audio_path, language=language)

        # 2. 클립 추출
        clip_result = extract_clips(
            url, stt_result,
            output_dir=output_dir,
            interval=interval,
            max_clips=max_clips
        )

        elapsed = time.time() - start_time

        # 상태 저장
        _clip_state["clips"] = clip_result["clips"]
        _clip_state["frames_dir"] = clip_result["frames_dir"]
        _clip_state["title"] = title

        # 마크다운 생성
        md_lines = [f"# {title} - 클립보드\n"]
        for c in clip_result["clips"]:
            md_lines.append(f"### [{c['time_str']}]")
            md_lines.append(f"![{c['time_str']}](frame_{c['index']:04d}.jpg)")
            if c.get("text"):
                md_lines.append(f"> {c['text']}")
            md_lines.append("")

        return jsonify({
            "title": title,
            "clips": clip_result["clips"],
            "scene_changes": clip_result["scene_changes"],
            "total_clips": clip_result["total_clips"],
            "elapsed": elapsed,
            "markdown": "\n".join(md_lines),
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/clips/frame/<int:index>")
def api_clips_frame(index):
    """프레임 이미지 서빙"""
    from flask import send_file
    frames_dir = _clip_state.get("frames_dir", "/tmp/stt-work/frames")
    frame_path = os.path.join(frames_dir, f"frame_{index:04d}.jpg")

    if os.path.exists(frame_path):
        return send_file(frame_path, mimetype="image/jpeg")
    else:
        # 1x1 투명 placeholder
        return "", 404


@app.route("/api/harness/files")
def api_harness_files():
    files = []

    for base_dir in [HARNESS_DIR, APP_HARNESS_DIR]:
        if base_dir.exists():
            for f in sorted(base_dir.rglob("*.md")):
                files.append(str(f.relative_to(PROJECT_ROOT)))

    for special in ["AGENTS.md", "CLAUDE.md"]:
        if (PROJECT_ROOT / special).exists():
            files.insert(0, special)

    # 개요
    overview = {
        "constitution": "있음" if (HARNESS_DIR / "core" / "constitution.md").exists() else "없음",
        "specs": f"{len(list((APP_HARNESS_DIR / 'specs').glob('*.md')))}개" if (APP_HARNESS_DIR / "specs").exists() else "0개",
        "tests": f"{len(list((PROJECT_ROOT / 'app' / 'stt' / 'tests').glob('*.py')))}개" if (PROJECT_ROOT / "app" / "stt" / "tests").exists() else "0개",
        "workflows": f"{len(list((HARNESS_DIR / 'workflows').glob('*.md')))}개" if (HARNESS_DIR / "workflows").exists() else "0개",
    }

    return jsonify({"files": files, "overview": overview})


@app.route("/api/harness/load")
def api_harness_load():
    path = request.args.get("path", "")
    full_path = PROJECT_ROOT / path

    if not full_path.exists():
        return jsonify({"content": "", "info": f"파일 없음: {path}"})

    content = full_path.read_text(encoding="utf-8")

    # 카테고리 판단
    if "core/" in path: cat = "레포 하네스 > 코어"
    elif "roles/" in path: cat = "레포 하네스 > 역할"
    elif "workflows/" in path: cat = "레포 하네스 > 워크플로우"
    elif "specs/" in path: cat = "앱 하네스 > 기능 명세"
    elif "docs/" in path: cat = "앱 하네스 > 문서"
    elif "plans/" in path: cat = "앱 하네스 > 로드맵"
    elif "references/" in path: cat = "앱 하네스 > 참고 자료"
    else: cat = "루트"

    info = f"{cat} | {path} | {len(content)}자, {content.count(chr(10))+1}줄"
    return jsonify({"content": content, "info": info})


@app.route("/api/harness/save", methods=["POST"])
def api_harness_save():
    data = request.json
    path = data.get("path", "")
    content = data.get("content", "")

    if not path:
        return jsonify({"error": "경로가 필요합니다."})

    full_path = PROJECT_ROOT / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")

    return jsonify({"message": f"저장 완료: {path} ({len(content)}자)"})


@app.route("/api/harness/create", methods=["POST"])
def api_harness_create():
    data = request.json
    name = data.get("name", "").strip()
    category = data.get("category", "harness/core/")

    if not name:
        return jsonify({"error": "파일 이름이 필요합니다."})

    if not name.endswith(".md"):
        name += ".md"

    rel_path = category + name
    full_path = PROJECT_ROOT / rel_path

    if full_path.exists():
        return jsonify({"error": "이미 존재하는 파일입니다."})

    full_path.parent.mkdir(parents=True, exist_ok=True)
    title = name.replace(".md", "").replace("-", " ").replace("_", " ").title()
    full_path.write_text(f"# {title}\n\n(내용을 작성해주세요)\n", encoding="utf-8")

    return jsonify({"path": rel_path, "message": f"생성 완료: {rel_path}"})


@app.route("/api")
def api_docs():
    return jsonify({
        "name": "Offline Thinking STT API",
        "version": "1.0",
        "base_url": "http://localhost:7860",
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/transcribe/youtube",
                "description": "YouTube URL을 텍스트로 변환",
                "request": {
                    "url": "string (required) — YouTube URL",
                    "language": "string (optional, default: 'ko') — 언어 코드",
                    "model": "string (optional) — mlx-whisper 모델명"
                },
                "response": {
                    "title": "string — 영상 제목",
                    "text": "string — STT 텍스트",
                    "markdown": "string — 타임스탬프 포함 마크다운",
                    "srt": "string — SRT 자막 형식",
                    "segments": "integer — 세그먼트 수",
                    "elapsed": "float — 소요 시간(초)"
                }
            },
            {
                "method": "POST",
                "path": "/api/transcribe/file",
                "description": "로컬 오디오/비디오 파일을 텍스트로 변환",
                "request": {
                    "file": "multipart/form-data (required) — 오디오/비디오 파일",
                    "language": "string (optional, default: 'ko')",
                    "model": "string (optional)"
                },
                "response": {
                    "markdown": "string",
                    "srt": "string",
                    "text": "string",
                    "segments": "integer",
                    "elapsed": "float"
                }
            },
            {
                "method": "POST",
                "path": "/api/clips/extract",
                "description": "YouTube 영상에서 장면별 클립(프레임+텍스트) 추출",
                "request": {
                    "url": "string (required)",
                    "language": "string (optional, default: 'ko')",
                    "interval": "integer (optional, default: 30) — 클립 간격(초)",
                    "max_clips": "integer (optional, default: 40) — 최대 클립 수"
                },
                "response": {
                    "title": "string",
                    "clips": "array — [{index, timestamp, time_str, text, frame_path}]",
                    "scene_changes": "integer",
                    "total_clips": "integer",
                    "elapsed": "float",
                    "markdown": "string"
                }
            },
            {
                "method": "GET",
                "path": "/api/clips/frame/<index>",
                "description": "추출된 프레임 이미지 반환 (JPEG)",
                "response": "image/jpeg"
            }
        ],
        "models": [
            "mlx-community/whisper-large-v3-turbo (default, 권장)",
            "mlx-community/whisper-large-v3 (최고 품질)",
            "mlx-community/whisper-small (가벼움)"
        ]
    })


if __name__ == "__main__":
    print("\\n===========================================")
    print("  Offline Thinking - STT & 하네스 편집기")
    print("  http://localhost:7860")
    print("===========================================\\n")
    app.run(host="0.0.0.0", port=7860, debug=False)
