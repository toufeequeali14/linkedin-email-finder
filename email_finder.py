# email_finder.py
import json
import os
import random
import sys

from email_token_generator import TokenGenerator

INPUT_FILE = "linkedin_urls.txt"   # one URL per line; blank lines and # comments are ignored
OUTPUT_FILE = "emails.json"
API_URL = "https://apiapp.anymailfinder.com/www/search"


def find_email(gen, linkedin_url):
    payload = {
        "recaptchaToken": gen.get_token(),   # fresh token, used immediately
        "searchLinkedinUrl": linkedin_url,
    }
    return gen.post_json(API_URL, payload)


def load_urls(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f]
    seen, urls = set(), []
    for ln in lines:
        if not ln or ln.startswith("#"):
            continue
        ln = ln.split("?")[0].rstrip("/") + "/"
        if "linkedin.com/in/" not in ln:
            print(f"[skip] not a profile URL: {ln}")
            continue
        if ln not in seen:
            seen.add(ln)
            urls.append(ln)
    return urls


def slim(url, status, body):
    """Reduce an API response to account, company, email."""
    if status not in (200, 201):
        return {"account": url, "error": status}
    results = (body.get("search") or {}).get("resultList") or []
    hit = next((r for r in results if r.get("email")), None)
    return {
        "account": url,
        "company": hit.get("company") if hit else None,
        "email": hit.get("email") if hit else None,
    }


def load_results(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError:
        return {}
    return {url: (slim(url, 201, v) if "search" in v else v) for url, v in raw.items()}


def save_results(path, results):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    urls = load_urls(input_file)

    results = load_results(OUTPUT_FILE)
    save_results(OUTPUT_FILE, results)
    todo = [u for u in urls if not (u in results and "error" not in results[u])]
    print(f"[*] {len(urls)} URLs loaded, {len(todo)} to process")
    if not todo:
        return

    gen = TokenGenerator()
    try:
        for i, u in enumerate(todo, 1):
            status, body = find_email(gen, u)
            if status == 403:
                gen.wait(15000)
                status, body = find_email(gen, u)

            results[u] = slim(u, status, body)
            save_results(OUTPUT_FILE, results)
            print(f"[{i}/{len(todo)}] {u} -> {status} | {results[u].get('email')}")

            if status == 403:
                print("[-] Still 403 after retry, stopping.")
                break
            gen.wait(random.uniform(4, 9) * 1000)
    finally:
        gen.close()


if __name__ == "__main__":
    main()