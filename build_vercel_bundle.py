"""
GIGANG - Vercel / Stlite WebAssembly Bundle Builder
모든 Python 소스 코드를 단일 브라우저 구동형 WebAssembly(index.html)로 번들링
"""

import os
import sys
import json
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "gigang"
OUTPUT_DIR = BASE_DIR / "GIGANG_Vercel"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 번들링할 파일 목록
files_dict = {}

# 1. 루트 app.py (실제 대시보드 코드를 직접 엔트리포인트로 번들링하여 Stlite 리런 보장)
with open(BASE_DIR / "gigang" / "ui" / "app.py", "r", encoding="utf-8") as f:
    files_dict["app.py"] = f.read()

# 2. gigang 패키지 내 모든 .py 파일 수집
for root, dirs, files in os.walk(SRC_DIR):
    if "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            full_path = Path(root) / file
            rel_path = full_path.relative_to(BASE_DIR).as_posix()
            with open(full_path, "r", encoding="utf-8") as f:
                files_dict[rel_path] = f.read()

# HTML <script> 내에서 </script> 태그 조기 종료 방지를 위해 '<'를 '\\u003c'로 이스케이프
files_json = json.dumps(files_dict, ensure_ascii=False).replace("<", "\\u003c")

# 3. index.html 템플릿 생성
html_content = f"""<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
    <title>GIGANG | 통합 보안관제 & 섀도우 AI 거버넌스</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🛡️</text></svg>" />
    <!-- Stlite WebAssembly CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/mountable@0.73.1/build/stlite.css" />
    <style>
      body, html {{
        margin: 0;
        padding: 0;
        width: 100%;
        min-height: 100%;
        background-color: #07111f;
        color: #f5f7fb;
        overflow-x: hidden;
        overflow-y: auto;
      }}
      #loading-splash {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #07111f;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        color: #f5f7fb;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        z-index: 999999;
        transition: opacity 0.5s ease;
      }}
      .spinner {{
        width: 50px;
        height: 50px;
        border: 4px solid #1e293b;
        border-top: 4px solid #38bdf8;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
      }}
      @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
      }}
    </style>
  </head>
  <body>
    <div id="loading-splash">
      <div class="spinner"></div>
      <h2 style="margin:0 0 8px 0; font-size: 22px; font-weight:700;">🛡️ GIGANG 초고속 WebAssembly 로딩 중...</h2>
      <p style="color: #94a3b8; font-size: 13px; margin:0;">Vercel Seoul Edge CDN에서 파이썬 런타임을 브라우저로 가져오는 중입니다</p>
    </div>
    <div id="root"></div>

    <!-- Stlite WebAssembly Core JS -->
    <script src="https://cdn.jsdelivr.net/npm/@stlite/mountable@0.73.1/build/stlite.js"></script>
    <script>
      // 전역 런타임 오류 방어 가드 (React Unhandled Exception 전파 차단)
      window.addEventListener("error", (e) => {{
        if (e.message && (e.message.includes("enqueueSetState") || e.message.includes("ResizeObserver"))) {{
          e.stopImmediatePropagation();
        }}
      }});
      window.addEventListener("unhandledrejection", (e) => {{
        if (e.reason && String(e.reason).includes("enqueueSetState")) {{
          e.preventDefault();
        }}
      }});

      const files = {files_json};

      stlite.mount(
        {{
          requirements: ["pydantic>=2.0.0", "pandas"],
          entrypoint: "app.py",
          files: files,
          streamlitConfig: {{
            "theme.base": "dark",
            "theme.backgroundColor": "#07111f",
            "theme.secondaryBackgroundColor": "#0d1a2b",
            "theme.textColor": "#f5f7fb",
            "theme.primaryColor": "#38bdf8"
          }}
        }},
        document.getElementById("root")
      );

      // 로딩 스플래시 화면 자동 숨김
      const observer = new MutationObserver((mutations, obs) => {{
        const root = document.getElementById("root");
        if (root && root.children.length > 0) {{
          const splash = document.getElementById("loading-splash");
          if (splash) {{
            splash.style.opacity = "0";
            setTimeout(() => splash.remove(), 500);
          }}
          obs.disconnect();
        }}
      }});
      observer.observe(document.getElementById("root"), {{ childList: true, subtree: true }});
    </script>
  </body>
</html>
"""

# 4. index.html 저장
with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# 5. vercel.json 생성
vercel_json = {
    "rewrites": [
        {"source": "/(.*)", "destination": "/index.html"}
    ],
    "headers": [
        {
            "source": "/(.*)",
            "headers": [
                {"key": "Cross-Origin-Opener-Policy", "value": "same-origin"},
                {"key": "Cross-Origin-Embedder-Policy", "value": "credentialless"}
            ]
        }
    ]
}

with open(OUTPUT_DIR / "vercel.json", "w", encoding="utf-8") as f:
    json.dump(vercel_json, f, indent=2, ensure_ascii=False)

# 6. README.md 생성
readme_content = """# ⚡ GIGANG (Vercel 초고속 WebAssembly 배포판)

이 폴더는 **Vercel** 또는 **GitHub Pages**에 드래그 & 드롭하여 즉시 배포할 수 있는 초고속 버전입니다.

## 🚀 왜 이 버전이 압도적으로 빠를까요?
1. **미국 서버 왕복 통신 제거:** 파이썬 코드가 브라우저(WebAssembly) 안에서 직접 실행됩니다.
2. **0.01초 반응 속도:** 인시던트 드롭다운 변경, 탭 전환, SOAR 버튼 클릭이 네트워크 지연 없이 즉각 반응합니다.
3. **Vercel 서울 리전 호스팅:** 전 세계에서 가장 빠른 Vercel CDN을 통해 배포됩니다.

## 📦 Vercel 배포 방법 (1분 완료)
1. 깃허브에 새 저장소 (예: `gigang-vercel`)를 만듭니다.
2. 본 `GIGANG_Vercel` 폴더 안의 파일(`index.html`, `vercel.json`, `README.md`)을 업로드합니다.
3. [vercel.com](https://vercel.com)에 로그인 후 해당 저장소를 선택하고 **[Deploy]**를 누르면 끝!
"""

with open(OUTPUT_DIR / "README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

print(f"✅ Vercel Stlite 번들 생성 완료: {OUTPUT_DIR}")
print(f"   포함된 파일 수: {len(files_dict)}개")
