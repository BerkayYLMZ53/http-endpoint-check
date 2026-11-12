"""Check HTTP status and response time from a local JSON configuration."""

import argparse
import http.client
import json
import math
import socket
import ssl
import sys
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def validate_keys(value, allowed, label):
    if not isinstance(value, dict) or value.keys() - allowed:
        raise ValueError(f"{label} nesnesinde beklenmeyen alan var")


def positive_number(value):
    if type(value) not in (int, float) or value <= 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def valid_url(url):
    if not isinstance(url, str) or not url.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in url):
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
        return (
            parts.scheme in ("http", "https") and bool(parts.hostname) and parts.username is None
            and not parts.fragment and (port is None or port > 0)
        )
    except ValueError:
        return False


def read_config(path):
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON biçim hatası, satır {error.lineno}") from None
    validate_keys(config, {"timeout_seconds", "endpoints"}, "Yapılandırma")
    timeout = config.get("timeout_seconds", 5)
    if not positive_number(timeout) or timeout > 600:
        raise ValueError("timeout_seconds 0'dan büyük ve en fazla 600 olmalı")
    endpoints = config.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError("endpoints en az bir öğe içermeli")

    names = set()
    for position, endpoint in enumerate(endpoints, 1):
        label = f"Uç nokta {position}"
        validate_keys(endpoint, {"name", "url", "expect", "method", "max_latency_ms"}, label)
        name = endpoint.get("name")
        if not isinstance(name, str) or not name.strip() or not name.isprintable() or name in names:
            raise ValueError(f"{label} için benzersiz ve yazdırılabilir bir ad gerekiyor")
        names.add(name)
        if not valid_url(endpoint.get("url")):
            raise ValueError(f"{label} geçerli bir HTTP veya HTTPS adresi içermeli")
        expected = endpoint.get("expect")
        if not isinstance(expected, list) or not expected or any(
            type(code) is not int or not 100 <= code <= 599 for code in expected
        ):
            raise ValueError(f"{label} için expect, 100–599 arası HTTP kodları içermeli")
        if endpoint.get("method", "GET") not in ("GET", "HEAD"):
            raise ValueError(f"{label} yöntemi GET veya HEAD olmalı")
        if "max_latency_ms" in endpoint and not positive_number(endpoint["max_latency_ms"]):
            raise ValueError(f"{label} için max_latency_ms pozitif sayı olmalı")
    return timeout, endpoints


def network_error(error):
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, TimeoutError):
        return "zaman aşımı"
    if isinstance(reason, ssl.SSLError):
        return "TLS bağlantı hatası"
    if isinstance(reason, socket.gaierror):
        return "DNS çözümleme hatası"
    return "bağlantı veya HTTP protokol hatası"


def check_endpoint(endpoint, timeout, opener):
    request = Request(endpoint["url"], method=endpoint.get("method", "GET"))
    start = perf_counter()
    status = None
    error = None
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
    except HTTPError as response:
        status = response.code
        response.close()
    except (OSError, ValueError, http.client.HTTPException) as failure:
        error = network_error(failure)
    elapsed_ms = (perf_counter() - start) * 1000
    if error is None:
        if status not in endpoint["expect"]:
            error = "beklenmeyen HTTP durumu"
        elif elapsed_ms > endpoint.get("max_latency_ms", math.inf):
            error = "yanıt süresi sınırı aşıldı"
    return {
        "name": endpoint["name"], "status": status, "expected": endpoint["expect"],
        "elapsed_ms": round(elapsed_ms, 1), "ok": error is None, "error": error,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Uç noktaların HTTP durumunu ve yanıt süresini denetle.")
    parser.add_argument("config", type=Path, help="Uç nokta listesi içeren JSON dosyası.")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yaz.")
    args = parser.parse_args(argv)

    try:
        timeout, endpoints = read_config(args.config)
    except (OSError, UnicodeError):
        print("Yapılandırma dosyası UTF-8 olarak okunamadı.", file=sys.stderr)
        return 2
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    opener = build_opener(NoRedirect())
    report = [check_endpoint(endpoint, timeout, opener) for endpoint in endpoints]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for result in report:
            status = f'HTTP {result["status"]}' if result["status"] is not None else "yanıt yok"
            outcome = result["error"] or "başarılı"
            print(f'{result["name"]} · {status} · {result["elapsed_ms"]} ms · {outcome}')
    return int(any(not result["ok"] for result in report))


if __name__ == "__main__":
    raise SystemExit(main())
