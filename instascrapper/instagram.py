import io
import json
import time
import zipfile
import datetime
import os
import requests
from typing import Optional
from camoufox.sync_api import Camoufox
from session import save_session, load_session

INSTAGRAM_URL = "https://www.instagram.com"


def _normalize_username(value: str) -> str:
    return (value or "").strip().lstrip("@").strip().lower()


def _extract_recent_posts_from_user_node(u: dict, limit: int = 12) -> list[dict]:
    """
    A partir do objeto `user` de web_profile_info, devolve posts recentes.
    O Instagram parou de incluir `edges` nesse endpoint; retorna [] quando vazio.
    Use _extract_recent_posts_from_feed_items() como fonte primária.
    """
    if not u or not isinstance(u, dict):
        return []
    out: list[dict] = []
    try:
        edges = (u.get("edge_owner_to_timeline_media") or {}).get("edges") or []
        for e in edges[:limit]:
            node = (e or {}).get("node") or {}
            if not node:
                continue
            likes = None
            elb = node.get("edge_liked_by")
            if isinstance(elb, dict) and "count" in elb:
                likes = elb.get("count")
            comments = None
            for key in (
                "edge_media_to_parent_comment",
                "edge_media_to_comment",
                "edge_media_to_hoisted_comment",
            ):
                c = node.get(key)
                if isinstance(c, dict) and c.get("count") is not None:
                    comments = c.get("count")
                    break
            shortcode = node.get("shortcode")
            img = node.get("display_url") or node.get("thumbnail_src")
            if node.get("__typename") == "GraphSidecar":
                ch = (node.get("edge_sidecar_to_children") or {}).get("edges") or []
                if ch and (ch[0].get("node") or {}).get("display_url"):
                    img = ch[0]["node"].get("display_url") or img
            caption_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
            caption = ((caption_edges[0].get("node") or {}).get("text") or "") if caption_edges else ""
            out.append(
                {
                    "shortcode": shortcode,
                    "permalink": f"{INSTAGRAM_URL}/p/{shortcode}/"
                    if shortcode
                    else None,
                    "image_url": img,
                    "typename": node.get("__typename"),
                    "is_pinned": bool(node.get("is_pinned")),
                    "likes": likes,
                    "comments": comments,
                    "caption": caption,
                }
            )
    except Exception:
        return []
    return out


def _extract_recent_posts_from_feed_items(items: list, limit: int = 12) -> list[dict]:
    """
    Converte itens do endpoint /api/v1/feed/user/<id>/ para o formato padrão de posts.
    media_type: 1=foto, 2=vídeo, 8=carrossel
    """
    if not items:
        return []
    out: list[dict] = []
    try:
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            shortcode = item.get("code")
            like_count = item.get("like_count")
            comment_count = item.get("comment_count")
            media_type = item.get("media_type", 1)
            caption_text = ""
            cap = item.get("caption")
            if isinstance(cap, dict):
                caption_text = cap.get("text") or ""
            elif isinstance(cap, str):
                caption_text = cap

            img = None
            if media_type == 8:
                # carrossel — pega a primeira imagem
                carousel = item.get("carousel_media") or []
                if carousel:
                    cands = (carousel[0].get("image_versions2") or {}).get("candidates") or []
                    if cands:
                        img = cands[0].get("url")
            if not img:
                cands = (item.get("image_versions2") or {}).get("candidates") or []
                if cands:
                    img = cands[0].get("url")

            typename_map = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}
            out.append({
                "shortcode": shortcode,
                "permalink": f"{INSTAGRAM_URL}/p/{shortcode}/" if shortcode else None,
                "image_url": img,
                "typename": typename_map.get(media_type, "GraphImage"),
                "is_pinned": bool(item.get("is_pinned")),
                "likes": like_count,
                "comments": comment_count,
                "caption": caption_text,
            })
    except Exception:
        return []
    return out


class InstagramClient:
    def __init__(self, headless: bool | str = "virtual"):
        self._headless = headless
        self._camoufox: Optional[Camoufox] = None
        self._browser = None
        self._page = None
        self._last_telemetry: dict = {}

    # ── context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        self._camoufox = Camoufox(headless=self._headless)
        self._browser = self._camoufox.__enter__()
        self._page = self._browser.new_page()
        return self

    def __exit__(self, *args):
        self._camoufox.__exit__(*args)

    # ── internal helpers ─────────────────────────────────────────────────────

    def _goto(self, url: str, wait: str = "domcontentloaded") -> None:
        self._page.goto(url, wait_until=wait)
        self._dismiss_cookie_banner()

    def _dismiss_cookie_banner(self) -> None:
        try:
            btn = self._page.locator("text=Allow all cookies").first
            if btn.is_visible(timeout=2000):
                btn.click()
        except Exception:
            pass

    def _wait_for_selector(self, selector: str, timeout: int = 10_000):
        return self._page.wait_for_selector(selector, timeout=timeout)

    def _is_logged_in(self) -> bool:
        self._page.goto(INSTAGRAM_URL, wait_until="domcontentloaded")
        time.sleep(2)
        return "login" not in self._page.url

    def _get_page_telemetry(self, stage: str, target_username: str = "") -> dict:
        html = ""
        title = ""
        url = ""
        body_text = ""
        try:
            url = self._page.url or ""
        except Exception:
            pass
        try:
            title = (self._page.title() or "")[:300]
        except Exception:
            pass
        try:
            html = self._page.content() or ""
        except Exception:
            pass
        try:
            body_text = (
                self._page.locator("body").inner_text(timeout=2_000) or ""
            )[:1000]
        except Exception:
            pass
        html_excerpt = " ".join((html or "")[:3000].split())
        looks_login = "login" in (url or "").lower() or "/accounts/login" in (url or "").lower()
        looks_logged_in = not looks_login
        telemetry = {
            "stage": stage,
            "target_username": target_username,
            "current_url": url,
            "page_title": title,
            "looks_like_login_page": looks_login,
            "looks_logged_in": looks_logged_in,
            "html_excerpt": html_excerpt[:1500],
            "body_excerpt": " ".join(body_text.split())[:800],
        }
        self._last_telemetry = telemetry
        return telemetry

    def _save_debug_artifacts(
        self,
        target_username: str,
        stage: str,
        out_dir: str = ".",
        extra: Optional[dict] = None,
    ) -> dict:
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_target = (target_username or "unknown").replace("/", "_")
        prefix = f"debug_{safe_target}_{stage}_{timestamp}"
        screenshot_path = os.path.join(out_dir, f"{prefix}.png")
        html_path = os.path.join(out_dir, f"{prefix}.html")
        json_path = os.path.join(out_dir, f"{prefix}.json")
        telemetry = self._get_page_telemetry(stage, target_username)
        if extra:
            telemetry.update(extra)
        try:
            self._page.screenshot(path=screenshot_path, full_page=True)
            telemetry["screenshot_path"] = screenshot_path
        except Exception as exc:
            telemetry["screenshot_error"] = str(exc)
        try:
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(self._page.content() or "")
            telemetry["html_path"] = html_path
        except Exception as exc:
            telemetry["html_error"] = str(exc)
        try:
            with open(json_path, "w", encoding="utf-8") as fh:
                json.dump(telemetry, fh, ensure_ascii=False, indent=2)
            telemetry["json_path"] = json_path
        except Exception as exc:
            telemetry["json_error"] = str(exc)
        self._last_telemetry = telemetry
        return telemetry

    def get_last_telemetry(self) -> dict:
        return dict(self._last_telemetry or {})

    # ── auth ─────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str, save: bool = True) -> bool:
        """Faz login no Instagram. Retorna True se bem-sucedido."""
        # Tenta carregar sessão salva primeiro
        self._goto(INSTAGRAM_URL)
        if load_session(self._page, username):
            try:
                self._page.reload(wait_until="domcontentloaded", timeout=60_000)
            except Exception:
                pass  # cookies já foram aplicados; continua mesmo se reload travar
            time.sleep(2)
            if self._is_logged_in():
                print("[login] Sessão restaurada com sucesso.")
                return True
            print("[login] Sessão expirada ou inválida.")

        if not str(password or "").strip():
            print(
                "[login] Sem credenciais para refazer o login. "
                "Rode: python3 instascrapper/main.py login <usuario> <senha>"
            )
            return False

        # Login manual — /accounts/login/ trava; usamos a homepage e clicamos
        # no botão "Entrar" caso o formulário não apareça inline (mobile view).
        self._page.set_viewport_size({"width": 1280, "height": 800})
        self._goto(f"{INSTAGRAM_URL}/")

        USER_SEL = (
            "input[name='username'], "
            "input[autocomplete='username'], "
            "input[placeholder*='username' i], "
            "input[placeholder*='Mobile' i], "
            "input[placeholder*='Número' i], "
            "input[aria-label*='username' i], "
            "input[aria-label*='Mobile' i]"
        )
        PASS_SEL = "input[name='password'], input[type='password']"

        # Se o formulário não estiver inline, clica em "Entrar" / "Log in"
        try:
            self._page.wait_for_selector(USER_SEL, timeout=5_000)
        except Exception:
            LOGIN_BTN = "a[href*='/accounts/login'], button:has-text('Entrar'), button:has-text('Log in'), a:has-text('Entrar'), a:has-text('Log in')"
            try:
                self._page.locator(LOGIN_BTN).first.click()
                self._page.wait_for_selector(USER_SEL, timeout=20_000)
            except Exception:
                self._page.screenshot(path="login_debug.png")
                print("[login] Campo de usuário não encontrado. Screenshot salvo em login_debug.png")
                return False

        self._page.locator(USER_SEL).first.fill(username)
        self._page.locator(PASS_SEL).first.fill(password)
        self._page.locator(PASS_SEL).first.press("Enter")

        # Aguarda redirecionamento pós-login
        try:
            self._page.wait_for_url(
                lambda url: "login" not in url, timeout=15_000
            )
        except Exception:
            print("[login] Falha no login. Verifique usuário/senha ou 2FA.")
            return False

        time.sleep(3)

        # Descarta popups de notificação
        try:
            not_now = self._page.locator("text=Not Now").first
            if not_now.is_visible(timeout=3000):
                not_now.click()
        except Exception:
            pass

        if save:
            save_session(self._page, username)

        print("[login] Login realizado com sucesso.")
        return True

    # ── profile scraping ─────────────────────────────────────────────────────

    def inspect(self, target_username: str, out_dir: str = ".") -> None:
        """Salva screenshot + HTML da página do perfil para análise de seletores."""
        import os
        target_username = _normalize_username(target_username)
        url = f"{INSTAGRAM_URL}/{target_username}/"
        print(f"[inspect] Navegando para {url}")
        self._goto(url)
        time.sleep(4)
        # Se redirecionou para login, registra isso também
        current = self._page.url
        print(f"[inspect] URL atual: {current}")
        img_path = os.path.join(out_dir, f"inspect_{target_username}.png")
        html_path = os.path.join(out_dir, f"inspect_{target_username}.html")
        self._page.screenshot(path=img_path, full_page=True)
        html = self._page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[inspect] Screenshot → {img_path}")
        print(f"[inspect] HTML       → {html_path}")

    def get_profile(self, target_username: str, out_dir: str = ".") -> dict:
        """Extrai informações do perfil via API interna do Instagram."""
        target_username = _normalize_username(target_username)
        profile_url = f"{INSTAGRAM_URL}/{target_username}/"
        api_url = f"{INSTAGRAM_URL}/api/v1/users/web_profile_info/?username={target_username}"

        # Navega para a página do perfil primeiro (garante cookies/sessão no contexto)
        self._page.set_viewport_size({"width": 1280, "height": 800})
        self._goto(profile_url)
        time.sleep(2)
        self._get_page_telemetry("profile_page_loaded", target_username)

        if "login" in self._page.url:
            print("[profile] Redirecionado para login — sessão inválida ou expirada.")
            telemetry = self._save_debug_artifacts(
                target_username,
                "profile_redirect_login",
                out_dir=out_dir,
            )
            return {
                "username": target_username,
                "url": profile_url,
                "error": "not_logged_in",
                "_telemetry": telemetry,
            }

        # Chama a API interna usando fetch() no contexto autenticado do browser
        resp_raw = self._page.evaluate(
            """async (url) => {
                try {
                    const r = await fetch(url, {
                        headers: {"x-ig-app-id": "936619743392459", "accept": "*/*"},
                        credentials: "include"
                    });
                    if (!r.ok) return {status: r.status, data: null};
                    return {status: r.status, data: await r.json()};
                } catch(e) {
                    return {status: 0, data: null, err: String(e)};
                }
            }""",
            api_url,
        )

        api_status = (resp_raw or {}).get("status", 0) if isinstance(resp_raw, dict) else 0
        raw = (resp_raw or {}).get("data") if isinstance(resp_raw, dict) else None

        if not raw:
            hint = {
                0:   "Erro de rede ou CORS bloqueou a chamada.",
                400: "Requisição inválida — username com caracteres especiais ou API mudou.",
                401: "Sessão expirada — faça login novamente: python3 main.py login <usuario> <senha>",
                403: "Acesso negado — conta pode estar bloqueada ou checkpoint pendente.",
                404: "Perfil não encontrado no Instagram.",
                429: "Rate limit — Instagram bloqueou temporariamente. Aguarde alguns minutos.",
            }.get(api_status, f"HTTP {api_status} — resposta inesperada da API.")
            print(f"[profile] API retornou status {api_status}: {hint}")
            telemetry = self._save_debug_artifacts(
                target_username,
                "profile_api_failed",
                out_dir=out_dir,
                extra={"api_url": api_url, "http_status": api_status},
            )
            error_code = {401: "session_expired", 403: "access_denied", 404: "not_found", 429: "rate_limited"}.get(api_status, "api_failed")
            return {
                "username": target_username,
                "url": profile_url,
                "error": error_code,
                "http_status": api_status,
                "hint": hint,
                "_telemetry": telemetry,
            }

        u = raw.get("data", {}).get("user", {})
        user_id = u.get("id") or u.get("pk") or ""

        # Busca posts via /api/v1/feed/user/ (web_profile_info não retorna edges)
        recent_posts: list[dict] = []
        if user_id:
            try:
                feed_url = f"{INSTAGRAM_URL}/api/v1/feed/user/{user_id}/?count=12"
                feed_raw = self._page.evaluate(
                    """async (url) => {
                        try {
                            const r = await fetch(url, {
                                headers: {"x-ig-app-id": "936619743392459", "accept": "*/*"},
                                credentials: "include"
                            });
                            if (!r.ok) return {status: r.status, items: null};
                            const d = await r.json();
                            return {status: r.status, items: d.items || null};
                        } catch(e) {
                            return {status: 0, items: null, err: String(e)};
                        }
                    }""",
                    feed_url,
                )
                feed_items = (feed_raw or {}).get("items") or []
                recent_posts = _extract_recent_posts_from_feed_items(feed_items, 12)
            except Exception as e:
                print(f"[profile] Aviso: falha ao buscar feed — {e}")
        # Fallback para edges legados caso existam
        if not recent_posts:
            recent_posts = _extract_recent_posts_from_user_node(u, 12)

        data: dict = {
            "username": target_username,
            "url": profile_url,
            "full_name": u.get("full_name"),
            "bio": u.get("biography"),
            "external_link": u.get("external_url") or None,
            "avatar_url": u.get("profile_pic_url_hd") or u.get("profile_pic_url"),
            "verified": u.get("is_verified", False),
            "private": u.get("is_private", False),
            "posts": str(u.get("edge_owner_to_timeline_media", {}).get("count", "")),
            "followers": str(u.get("edge_followed_by", {}).get("count", "")),
            "following": str(u.get("edge_follow", {}).get("count", "")),
            "recent_posts": recent_posts,
        }
        try:
            data["page_title"] = (self._page.title() or "")[:300]
        except Exception:
            pass
        data["_telemetry"] = self._get_page_telemetry("profile_api_ok", target_username)
        return data

    def scrape_profile(self, target_username: str, out_dir: str = ".") -> str:
        """
        Raspa o perfil: screenshot, avatar, até 6 posts fixados + 3 seguintes.
        Empacota tudo num ZIP e retorna o caminho do arquivo.
        """
        target_username = _normalize_username(target_username)
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{target_username}_{timestamp}"

        profile_url = f"{INSTAGRAM_URL}/{target_username}/"
        api_url = f"{INSTAGRAM_URL}/api/v1/users/web_profile_info/?username={target_username}"

        self._page.set_viewport_size({"width": 1280, "height": 800})
        self._goto(profile_url)
        time.sleep(3)
        self._get_page_telemetry("scrape_profile_loaded", target_username)

        if "login" in self._page.url:
            self._save_debug_artifacts(
                target_username,
                "scrape_redirect_login",
                out_dir=out_dir,
            )
            raise RuntimeError("Sessão inválida ou expirada.")

        # API interna
        resp_raw = self._page.evaluate(
            """async (url) => {
                try {
                    const r = await fetch(url, {
                        headers: {"x-ig-app-id": "936619743392459", "accept": "*/*"},
                        credentials: "include"
                    });
                    if (!r.ok) return {status: r.status, data: null};
                    return {status: r.status, data: await r.json()};
                } catch(e) {
                    return {status: 0, data: null, err: String(e)};
                }
            }""",
            api_url,
        )

        api_status = (resp_raw or {}).get("status", 0) if isinstance(resp_raw, dict) else 0
        raw = (resp_raw or {}).get("data") if isinstance(resp_raw, dict) else None

        if not raw:
            hint = {
                0:   "Erro de rede ou CORS.",
                400: "Requisição inválida (username com caracteres especiais ou API mudou).",
                401: "Sessão expirada — rode: python3 main.py login homeunity <senha>",
                403: "Acesso negado — checkpoint ou conta bloqueada.",
                404: "Perfil não encontrado.",
                429: "Rate limit — aguarde alguns minutos.",
            }.get(api_status, f"HTTP {api_status}.")
            print(f"[scrape] API retornou status {api_status}: {hint}")
            self._save_debug_artifacts(
                target_username,
                "scrape_api_failed",
                out_dir=out_dir,
                extra={"api_url": api_url, "http_status": api_status},
            )
            raise RuntimeError(f"API do Instagram retornou HTTP {api_status}: {hint}")

        u = raw.get("data", {}).get("user", {})
        user_id = u.get("id") or u.get("pk") or ""

        # Screenshot da viewport (não full_page para ficar menor)
        screenshot_bytes = self._page.screenshot(full_page=False)

        # Busca posts via /api/v1/feed/user/ (web_profile_info não retorna edges)
        feed_items: list[dict] = []
        if user_id:
            try:
                feed_url = f"{INSTAGRAM_URL}/api/v1/feed/user/{user_id}/?count=12"
                feed_raw = self._page.evaluate(
                    """async (url) => {
                        try {
                            const r = await fetch(url, {
                                headers: {"x-ig-app-id": "936619743392459", "accept": "*/*"},
                                credentials: "include"
                            });
                            if (!r.ok) return {status: r.status, items: null};
                            const d = await r.json();
                            return {status: r.status, items: d.items || null};
                        } catch(e) {
                            return {status: 0, items: null, err: String(e)};
                        }
                    }""",
                    feed_url,
                )
                feed_items = (feed_raw or {}).get("items") or []
                print(f"[scrape] Feed retornou {len(feed_items)} posts.")
            except Exception as e:
                print(f"[scrape] Aviso: falha ao buscar feed — {e}")

        # Seleciona até 9 posts: pinados primeiro, depois recentes
        pinned_items = [it for it in feed_items if it.get("is_pinned")]
        other_items = [it for it in feed_items if not it.get("is_pinned")]
        if pinned_items:
            selected_items = pinned_items[:6] + other_items[:3]
        else:
            selected_items = feed_items[:9]

        # Sessão requests para baixar imagens (CDN não requer auth, mas passa UA)
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.instagram.com/",
        })

        def _download(url: str) -> bytes | None:
            try:
                r = sess.get(url, timeout=15)
                r.raise_for_status()
                return r.content
            except Exception as e:
                print(f"[scrape] Aviso: falha ao baixar {url[:60]}… — {e}")
                return None

        # Avatar
        avatar_url = u.get("profile_pic_url_hd") or u.get("profile_pic_url")
        avatar_bytes = _download(avatar_url) if avatar_url else None

        # Imagens dos posts selecionados
        post_images: list[tuple[str, bytes]] = []
        selected_posts_meta = []
        for i, item in enumerate(selected_items, 1):
            shortcode = item.get("code")
            media_type = item.get("media_type", 1)
            is_pinned = bool(item.get("is_pinned"))
            label = "pinned" if is_pinned else "post"
            fname = f"{label}_{i:02d}.jpg"

            img_url = None
            if media_type == 8:
                carousel = item.get("carousel_media") or []
                if carousel:
                    cands = (carousel[0].get("image_versions2") or {}).get("candidates") or []
                    if cands:
                        img_url = cands[0].get("url")
            if not img_url:
                cands = (item.get("image_versions2") or {}).get("candidates") or []
                if cands:
                    img_url = cands[0].get("url")

            if img_url:
                img_data = _download(img_url)
                if img_data:
                    post_images.append((fname, img_data))

            cap = item.get("caption")
            caption = (cap.get("text") or "") if isinstance(cap, dict) else (cap or "")
            typename_map = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}
            selected_posts_meta.append({
                "filename": fname,
                "shortcode": shortcode,
                "permalink": f"{INSTAGRAM_URL}/p/{shortcode}/" if shortcode else None,
                "is_pinned": is_pinned,
                "typename": typename_map.get(media_type, "GraphImage"),
                "likes": item.get("like_count"),
                "comments": item.get("comment_count"),
                "caption": caption,
            })

        recent_posts = _extract_recent_posts_from_feed_items(feed_items, 12)
        if not recent_posts:
            recent_posts = _extract_recent_posts_from_user_node(u, 12)

        # Profile JSON
        profile_data = {
            "username": target_username,
            "full_name": u.get("full_name"),
            "bio": u.get("biography"),
            "followers": u.get("edge_followed_by", {}).get("count"),
            "following": u.get("edge_follow", {}).get("count"),
            "posts_count": u.get("edge_owner_to_timeline_media", {}).get("count"),
            "verified": u.get("is_verified"),
            "private": u.get("is_private"),
            "external_url": u.get("external_url"),
            "avatar_url": avatar_url,
            "scraped_at": timestamp,
            "recent_posts": recent_posts,
            "selected_posts": selected_posts_meta,
        }

        # Monta ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                f"{base_name}/profile.json",
                json.dumps(profile_data, indent=2, ensure_ascii=False),
            )
            zf.writestr(f"{base_name}/screenshot.png", screenshot_bytes)
            if avatar_bytes:
                zf.writestr(f"{base_name}/avatar.jpg", avatar_bytes)
            for fname, img_bytes in post_images:
                zf.writestr(f"{base_name}/posts/{fname}", img_bytes)

        zip_path = f"{out_dir}/{base_name}.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_buffer.getvalue())

        print(f"[scrape] ZIP gerado: {zip_path}  ({len(post_images)} imagens de posts)")
        return zip_path

    def analyze_profile(self, target_username: str) -> dict:
        """Retorna dados do perfil + análise derivada."""
        target_username = _normalize_username(target_username)
        profile = self.get_profile(target_username)
        analysis = self._derive_analysis(profile)
        return {"profile": profile, "analysis": analysis}

    @staticmethod
    def _derive_analysis(profile: dict) -> dict:
        analysis: dict = {}

        # Engajamento estimado (apenas com seguidores, sem dados de posts)
        followers_raw = profile.get("followers") or "0"
        followers_str = (
            followers_raw.replace(",", "").replace(".", "").replace(" ", "")
        )
        try:
            followers = int(followers_str)
        except ValueError:
            # handles "1.2M", "45K" etc
            followers = _parse_abbreviated(followers_raw)

        analysis["followers_int"] = followers

        if followers == 0:
            analysis["tier"] = "unknown"
        elif followers < 1_000:
            analysis["tier"] = "nano (< 1K)"
        elif followers < 10_000:
            analysis["tier"] = "micro (1K–10K)"
        elif followers < 100_000:
            analysis["tier"] = "mid-tier (10K–100K)"
        elif followers < 1_000_000:
            analysis["tier"] = "macro (100K–1M)"
        else:
            analysis["tier"] = "mega (> 1M)"

        # Bio keywords
        bio = profile.get("bio") or ""
        analysis["bio_length"] = len(bio)
        analysis["bio_has_emoji"] = any(
            ord(c) > 127 for c in bio
        )
        analysis["bio_has_link_mention"] = any(
            kw in bio.lower() for kw in ["http", "www", "link", "linktree"]
        )

        analysis["is_business_likely"] = (
            profile.get("external_link") is not None
            or analysis["bio_has_link_mention"]
        )
        analysis["is_verified"] = profile.get("verified", False)
        analysis["is_private"] = profile.get("private", False)

        return analysis


def _parse_abbreviated(value: str) -> int:
    value = value.strip().replace(",", ".").upper()
    try:
        if value.endswith("M"):
            return int(float(value[:-1]) * 1_000_000)
        if value.endswith("K"):
            return int(float(value[:-1]) * 1_000)
        return int(float(value))
    except Exception:
        return 0
