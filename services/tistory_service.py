import os
import re
from datetime import datetime
from typing import List, Optional
from playwright.async_api import async_playwright, Page


BLOG_NAME = os.getenv("TISTORY_BLOG_NAME", "kcl3598")


async def _click_submit(page: Page):
    for sel in [
        "button[type='submit']", "input[type='submit']",
        "button.btn_g", "button.btn_confirm",
        "button:has-text('로그인')", "button:has-text('다음')",
    ]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.click()
                return
        except Exception:
            continue
    await page.keyboard.press("Enter")


async def _login(page: Page):
    email = os.getenv("TISTORY_ID", "")
    password = os.getenv("TISTORY_PASSWORD", "")

    await page.goto("https://www.tistory.com/auth/login", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3000)

    for sel in [
        "a[href*='kakao']", "button[class*='kakao']",
        "a:has-text('카카오')", "button:has-text('카카오')",
        ".btn_login.link_kakao_id", ".kakao_login",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(2000)
                break
        except Exception:
            continue

    for sel in [
        "input#loginKey", "input[name='loginKey']",
        "input#loginId", "input[name='loginId']",
        "input[type='email']", "input[placeholder*='이메일']",
        "input[placeholder*='아이디']",
    ]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.fill(email)
                break
        except Exception:
            continue

    await _click_submit(page)
    await page.wait_for_timeout(2000)

    for sel in ["input#password", "input[name='password']", "input[type='password']"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=3000):
                await el.fill(password)
                break
        except Exception:
            continue

    await _click_submit(page)
    try:
        await page.wait_for_url("**/tistory.com/**", timeout=15000)
    except Exception:
        pass
    await page.wait_for_load_state("networkidle", timeout=10000)

    if "tistory.com" not in page.url:
        raise Exception(f"로그인 실패 - URL: {page.url}")


async def _set_content(page: Page, content: str):
    """본문 입력 - CodeMirror setValue → textarea → 클립보드 → HTML 모드 순으로 시도"""
    await page.wait_for_timeout(1000)

    # ── 방법 1: CodeMirror setValue (마크다운 모드가 이미 전환된 상태) ──
    try:
        # CodeMirror setValue + 검증
        char_len = await page.evaluate("""(content) => {
            const cmEl = document.querySelector('.CodeMirror');
            if (!cmEl || !cmEl.CodeMirror) return 0;
            const cm = cmEl.CodeMirror;
            cm.setValue(content);
            cm.refresh();
            return cm.getValue().length;
        }""", content)

        if char_len and char_len > 50:
            print(f"[OK] CodeMirror setValue 성공: {char_len}자")
            return

    except Exception as e:
        print(f"[WARN] 마크다운 모드 실패: {e}")

    # ── 방법 2: CodeMirror textarea에 직접 입력 ────────────────────────
    try:
        textarea = page.locator(".CodeMirror textarea").first
        if await textarea.is_visible(timeout=2000):
            await textarea.click()
            await page.keyboard.press("Control+a")
            await page.wait_for_timeout(300)
            await textarea.fill(content)
            await page.wait_for_timeout(500)

            char_len = await page.evaluate("""() => {
                const cm = document.querySelector('.CodeMirror')?.CodeMirror;
                return cm ? cm.getValue().length : 0;
            }""")
            if char_len and char_len > 50:
                print(f"[OK] CodeMirror textarea 입력 성공: {char_len}자")
                return
    except Exception as e:
        print(f"[WARN] CodeMirror textarea 실패: {e}")

    # ── 방법 3: 클립보드 붙여넣기 ─────────────────────────────────────
    try:
        await page.evaluate("(t) => navigator.clipboard.writeText(t)", content)
        for sel in [".CodeMirror", ".editor-content", "[contenteditable='true']"]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    await el.click()
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Control+v")
                    await page.wait_for_timeout(800)
                    print(f"[OK] 클립보드 붙여넣기 ({sel})")
                    return
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] 클립보드 실패: {e}")

    # ── 방법 4: TinyMCE (기본 에디터) HTML로 입력 ────────────────────
    try:
        # HTML 변환 (간단한 마크다운 → HTML)
        html_content = _markdown_to_html(content)

        result = await page.evaluate("""(html) => {
            if (window.tinymce && tinymce.activeEditor) {
                tinymce.activeEditor.setContent(html);
                return 'tinymce: ' + tinymce.activeEditor.getContent().length;
            }
            return null;
        }""", html_content)
        if result:
            print(f"[OK] TinyMCE: {result}")
            return

        # ProseMirror / contenteditable
        method = await page.evaluate("""(html) => {
            const pm = document.querySelector('.ProseMirror');
            if (pm) {
                pm.focus();
                pm.innerHTML = html;
                pm.dispatchEvent(new InputEvent('input', {bubbles: true}));
                return 'prosemirror:' + pm.innerHTML.length;
            }
            const editors = [...document.querySelectorAll('[contenteditable="true"]')]
                .filter(e => !e.closest('#post-title-inp, .title-area'));
            for (const el of editors) {
                el.focus();
                el.innerHTML = html;
                el.dispatchEvent(new InputEvent('input', {bubbles: true}));
                return 'contenteditable:' + el.innerHTML.length;
            }
            return null;
        }""", html_content)
        if method:
            print(f"[OK] JS 주입: {method}")
            return

    except Exception as e:
        print(f"[WARN] TinyMCE/ProseMirror 실패: {e}")

    print("[ERROR] 모든 본문 입력 방법 실패")


def _markdown_to_html(md: str) -> str:
    """마크다운을 기본 HTML로 변환합니다."""
    lines = md.split("\n")
    html_lines = []
    for line in lines:
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            # 볼드/이탤릭 처리
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)


async def _set_title(page: Page, title: str):
    for sel in [
        "input#post-title-inp", "textarea#post-title-inp",
        "input[name='title']", "input[placeholder*='제목']",
        ".title-area input", ".editor-title input",
    ]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1500):
                await el.fill(title)
                return
        except Exception:
            continue

    await page.evaluate("""(t) => {
        const el = document.querySelector('#post-title-inp') ||
                   document.querySelector('input[name=title]') ||
                   [...document.querySelectorAll('input')].find(e => e.placeholder?.includes('제목'));
        if (el) {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (setter) setter.set.call(el, t);
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }
    }""", title)


async def _upload_images_get_markdown(page: Page, image_paths: List[str]) -> str:
    """이미지를 티스토리에 업로드하고 삽입된 마크다운 이미지 태그를 반환합니다."""
    if not image_paths:
        return ""

    # 에디터 비우기
    await page.evaluate("""() => {
        const cm = document.querySelector('.CodeMirror')?.CodeMirror;
        if (cm) cm.setValue('');
    }""")

    for img_path in image_paths:
        try:
            before = await page.evaluate("""() => {
                const cm = document.querySelector('.CodeMirror')?.CodeMirror;
                return cm ? cm.getValue() : '';
            }""")

            # 이미지 업로드 버튼 클릭 → 파일 선택
            uploaded = False
            for sel in [
                "button[title*='사진']", "button[aria-label*='이미지']",
                "button[aria-label*='사진']", ".btn-image",
                "button.image-btn", "label[for*='image']",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.click()
                        fc = await fc_info.value
                        await fc.set_files(img_path)
                        await page.wait_for_timeout(3000)
                        uploaded = True
                        break
                except Exception:
                    continue

            if not uploaded:
                print(f"[WARN] 이미지 업로드 버튼 없음: {img_path}")
                continue

            # 업로드 후 삽입된 내용 확인
            after = await page.evaluate("""() => {
                const cm = document.querySelector('.CodeMirror')?.CodeMirror;
                return cm ? cm.getValue() : '';
            }""")

            if len(after) > len(before):
                print(f"[OK] 이미지 업로드 성공: {img_path}")
            else:
                print(f"[WARN] 이미지 업로드 후 변화 없음: {img_path}")

        except Exception as e:
            print(f"[WARN] 이미지 업로드 실패: {img_path}: {e}")

    # 업로드된 이미지 마크다운 수집
    image_markdown = await page.evaluate("""() => {
        const cm = document.querySelector('.CodeMirror')?.CodeMirror;
        return cm ? cm.getValue() : '';
    }""")

    return image_markdown


async def _set_tags(page: Page, tags: List[str]):
    for tag in tags[:15]:
        try:
            el = page.locator("#tagText").first
            if not await el.is_visible(timeout=2000):
                break
            await el.fill(tag)
            await el.press("Enter")
            await page.wait_for_timeout(300)
        except Exception:
            break


async def _publish(page: Page, scheduled_at: Optional[str] = None):
    """완료 버튼 → 발행 패널 → 발행."""
    for sel in ["button:has-text('완료')", "button.btn-posting-commit"]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await page.wait_for_timeout(2000)
                break
        except Exception:
            continue

    if scheduled_at:
        try:
            for sel in ["input[value='scheduled']", "label:has-text('예약')", "button:has-text('예약')"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue
            dt = datetime.fromisoformat(scheduled_at)
            for sel in ["input[type='datetime-local']", "input.date-schedule"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.fill(dt.strftime("%Y-%m-%dT%H:%M"))
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[예약 발행 설정 실패] {e}")

    for sel in [
        ".publish-layer button:has-text('발행')",
        ".layer-publish button:has-text('발행')",
        ".btn-publish-confirm",
        "button.btn-publish",
        "button:has-text('발행')",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await page.wait_for_timeout(3000)
                break
        except Exception:
            continue

    await page.wait_for_load_state("networkidle", timeout=15000)


async def post_to_tistory(
    title: str,
    content: str,
    tags: List[str],
    image_paths: Optional[List[str]] = None,
    scheduled_at: Optional[str] = None,
    headless: bool = False,
) -> dict:
    blog_name = os.getenv("TISTORY_BLOG_NAME", BLOG_NAME)
    result = {"success": False, "url": None, "error": None}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await context.grant_permissions(["clipboard-read", "clipboard-write"])

        page = await context.new_page()

        try:
            await _login(page)

            await page.goto(
                f"https://{blog_name}.tistory.com/manage/newpost/?type=post",
                wait_until="networkidle",
                timeout=30000,
            )
            await page.wait_for_timeout(3000)

            # 제목 입력
            await _set_title(page, title)
            await page.wait_for_timeout(500)

            # 마크다운 모드 전환 (이미지 업로드 전 먼저 전환)
            for sel in ["#editor-mode-layer-btn-open", "button[aria-label*='에디터 모드']"]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        await page.wait_for_timeout(800)
                        break
                except Exception:
                    continue
            for sel in ["#editor-mode-markdown", "button:has-text('마크다운')", "li:has-text('마크다운')"]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await page.wait_for_timeout(2500)
                        break
                except Exception:
                    continue

            # 이미지 업로드 → 에디터에 이미지 마크다운 자동 삽입
            image_markdown = ""
            if image_paths:
                image_markdown = await _upload_images_get_markdown(page, image_paths)

            # 이미지 + 본문 합쳐서 설정
            full_content = (image_markdown + "\n\n" + content).strip() if image_markdown else content
            await _set_content(page, full_content)
            await page.wait_for_timeout(1000)

            # 태그 입력
            await _set_tags(page, tags)
            await page.wait_for_timeout(500)

            # 발행
            await _publish(page, scheduled_at)

            # 발행된 URL 추출
            current_url = page.url
            post_match = re.search(rf"{blog_name}\.tistory\.com/(\d+)", current_url)
            if post_match:
                post_url = f"https://{blog_name}.tistory.com/{post_match.group(1)}"
            else:
                try:
                    await page.goto(
                        f"https://{blog_name}.tistory.com/manage/posts",
                        wait_until="networkidle",
                        timeout=15000,
                    )
                    links = await page.evaluate(f"""() => {{
                        const links = document.querySelectorAll('a[href*="{blog_name}.tistory.com/"]');
                        return [...links].map(a => a.href).filter(h => /\\/\\d+$/.test(h));
                    }}""")
                    post_url = links[0] if links else current_url
                except Exception:
                    post_url = current_url

            result["success"] = True
            result["url"] = post_url

        except Exception as e:
            result["error"] = str(e)
        finally:
            await browser.close()

    return result
