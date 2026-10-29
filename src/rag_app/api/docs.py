from fastapi import APIRouter
from fastapi.responses import HTMLResponse


def build_docs_router(title: str) -> APIRouter:
    router = APIRouter(tags=["docs"])
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} API</title>
  <style>
    body {{
      margin: 0;
      font: 15px/1.5 system-ui, sans-serif;
      color: #172033;
      background: #f5f7fa;
    }}
    main {{ max-width: 960px; margin: 40px auto; padding: 0 24px; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    p {{ color: #5d687a; }}
    section {{ margin-top: 28px; }}
    article {{
      background: white;
      border: 1px solid #dce2ea;
      border-radius: 6px;
      padding: 14px 16px;
      margin: 8px 0;
    }}
    code {{ font-family: ui-monospace, monospace; }}
    .method {{
      display: inline-block;
      min-width: 58px;
      font-weight: 700;
      color: #075985;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>本地 API 索引。原始规范：<a href="/openapi.json">/openapi.json</a></p>
    <section id="paths">加载接口中...</section>
  </main>
  <script>
    fetch('/openapi.json').then(r => r.json()).then(spec => {{
      const root = document.getElementById('paths');
      root.innerHTML = Object.entries(spec.paths).map(([path, methods]) =>
        Object.entries(methods).map(([method, operation]) =>
          `<article><span class="method">${{method.toUpperCase()}}</span>` +
          `<code>${{path}}</code><div>${{operation.summary || ''}}</div></article>`
        ).join('')
      ).join('');
    }}).catch(error => {{
      document.getElementById('paths').textContent = '加载失败: ' + error;
    }});
  </script>
</body>
</html>"""

    @router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    def docs() -> HTMLResponse:
        return HTMLResponse(html)

    return router
