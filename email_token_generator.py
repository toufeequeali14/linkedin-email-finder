# token_generator.py
import json
import os
from playwright.sync_api import sync_playwright

TARGET_URL = "https://anymailfinder.com/email-finder/from-linkedin"
INPUT_SELECTOR = "input.search-box_input__GrHQu"
SUBMIT_SELECTOR = 'button[type="submit"], button:has-text("Find"), button:has-text("Search")'
ACTION_CACHE = "recaptcha_action.json"
DISCOVERY_URL = "https://www.linkedin.com/in/abdul-sami-56a71224a/"

HOOK_JS = """
(() => {
  window.__rc = [];
  const wrap = (g) => {
    if (!g || !g.execute || g.__hooked) return;
    g.__hooked = true;
    const o = g.execute.bind(g);
    g.execute = function(k, opts) {
      window.__rc.push({key: k, opts: opts || null});
      return o(k, opts);
    };
  };
  const t = setInterval(() => {
    if (window.grecaptcha) {
      wrap(window.grecaptcha);
      if (window.grecaptcha.enterprise) wrap(window.grecaptcha.enterprise);
    }
  }, 20);
})();
"""

EXECUTE_JS = """async ([key, action]) => {
    const g = (window.grecaptcha.enterprise && window.grecaptcha.enterprise.execute)
        ? window.grecaptcha.enterprise : window.grecaptcha;
    await new Promise(r => g.ready(r));
    return await g.execute(key, action ? {action} : undefined);
}"""

POST_JS = """async ([api, payload]) => {
    const res = await fetch(api, {
        method: 'POST',
        credentials: 'include',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify(payload),
    });
    const text = await res.text();
    let body; try { body = JSON.parse(text); } catch { body = text; }
    return {status: res.status, body};
}"""


class TokenGenerator:
    def __init__(self, profile_dir="./pw_profile", headless=False):
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(profile_dir, headless=headless)
        self.ctx.add_init_script(HOOK_JS)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.goto(TARGET_URL, wait_until="networkidle")
        self.page.wait_for_function("() => window.grecaptcha", timeout=20000)

        self.site_key, self.action = None, None
        if os.path.exists(ACTION_CACHE):
            with open(ACTION_CACHE) as f:
                c = json.load(f)
            self.site_key, self.action = c["key"], c["action"]
        else:
            self._discover()

    def _discover(self):
        """One real UI search (costs one credit) to learn the site key and action."""
        self.page.wait_for_selector(INPUT_SELECTOR, timeout=15000)
        self.page.fill(INPUT_SELECTOR, DISCOVERY_URL)
        with self.page.expect_request(lambda r: "/www/search" in r.url and r.method == "POST", timeout=30000):
            self.page.click(SUBMIT_SELECTOR)
        calls = self.page.evaluate("window.__rc")
        print("[discover] execute() calls:", calls)
        if not calls:
            raise RuntimeError("No grecaptcha.execute call observed")
        last = calls[-1]
        self.site_key = last["key"]
        self.action = (last["opts"] or {}).get("action")
        with open(ACTION_CACHE, "w") as f:
            json.dump({"key": self.site_key, "action": self.action}, f)
        print(f"[discover] key={self.site_key} action={self.action!r}")
        self.page.wait_for_timeout(3000)

    def get_token(self):
        """Mint a fresh single-use reCAPTCHA token. Call once per request."""
        return self.page.evaluate(EXECUTE_JS, [self.site_key, self.action])

    def post_json(self, url, payload):
        """POST from inside the browser page (same cookies, TLS and headers as the site)."""
        r = self.page.evaluate(POST_JS, [url, payload])
        return r["status"], r["body"]

    def wait(self, ms):
        self.page.wait_for_timeout(int(ms))

    def close(self):
        self.ctx.close()
        self._pw.stop()