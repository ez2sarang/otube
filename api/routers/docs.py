"""API 문서 서빙 라우터"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse
import os

router = APIRouter(prefix="/api")

DOC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "doc", "API_REFERENCE.md")


@router.get("/docs/reference", response_class=PlainTextResponse)
async def get_docs_markdown():
    """API_REFERENCE.md를 마크다운 텍스트로 반환"""
    with open(DOC_PATH, encoding="utf-8") as f:
        return f.read()


@router.get("/docs/reference.html", response_class=HTMLResponse)
async def get_docs_html():
    """API_REFERENCE.md를 HTML로 렌더링해서 반환"""
    with open(DOC_PATH, encoding="utf-8") as f:
        md = f.read()
    # 간단한 마크다운 → HTML 변환 (markdown 패키지 없이)
    # marked.js (CDN)를 사용해서 클라이언트 사이드에서 렌더링
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Offline Thinking API Reference</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  pre {{ background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  h1, h2, h3 {{ border-bottom: 1px solid #eee; padding-bottom: 8px; }}
</style>
</head><body>
<div id="content"></div>
<script>
  const md = {repr(md)};
  document.getElementById('content').innerHTML = marked.parse(md);
</script>
</body></html>""")
