# SPDX-License-Identifier: GPL-3.0-or-later
"""SuRigandAnim - self-signed certificate for the live mocap server.

Browsers only give a web page the camera on a secure (HTTPS) origin, so the
phone needs an HTTPS address.  Blender on Windows and macOS does not ship the
``openssl`` command, so the certificate is built here in pure Python (RSA
key generation, DER encoding, PKCS#1 v1.5 SHA-256 signature).  The ``ssl``
module that Blender already bundles then loads the PEM files.

The certificate lists the server's LAN address, 127.0.0.1 and localhost in its
Subject Alternative Name, and is valid for 825 days.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import ipaddress
import secrets

_SMALL_PRIMES = [p for p in range(3, 2000, 2)
                 if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _is_probable_prime(n: int, rounds: int = 24) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


# ---------------------------------------------------------------------------
# DER helpers
# ---------------------------------------------------------------------------
def _length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, body: bytes) -> bytes:
    return bytes([tag]) + _length(len(body)) + body


def _int(value: int) -> bytes:
    body = value.to_bytes((value.bit_length() + 8) // 8, "big")
    return _tlv(0x02, body)


def _seq(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _oid(encoded: bytes) -> bytes:
    return _tlv(0x06, encoded)


_OID_RSA = _oid(bytes.fromhex("2a864886f70d010101"))
_OID_SHA256_RSA = _oid(bytes.fromhex("2a864886f70d01010b"))
_OID_CN = _oid(bytes.fromhex("550403"))
_OID_SAN = _oid(bytes.fromhex("551d11"))
_NULL = b"\x05\x00"
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _name(common_name: str) -> bytes:
    attr = _seq(_OID_CN, _tlv(0x0C, common_name.encode("utf-8")))
    return _seq(_tlv(0x31, attr))


def _time(moment: datetime.datetime) -> bytes:
    return _tlv(0x17, moment.strftime("%y%m%d%H%M%SZ").encode("ascii"))


def _general_names(ips: list[str], dns: list[str]) -> bytes:
    parts = []
    for ip in ips:
        parts.append(_tlv(0x87, ipaddress.ip_address(ip).packed))
    for name in dns:
        parts.append(_tlv(0x82, name.encode("ascii")))
    return _seq(*parts)


def _pem(label: str, der: bytes) -> str:
    text = base64.b64encode(der).decode("ascii")
    lines = [text[i:i + 64] for i in range(0, len(text), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def generate(lan_ip: str, days: int = 825, bits: int = 2048):
    """Return (cert_pem, key_pem, cert_der) for a self-signed server certificate."""
    half = bits // 2
    e = 65537
    while True:
        p = _random_prime(half)
        q = _random_prime(half)
        n = p * q
        phi = (p - 1) * (q - 1)
        if p != q and n.bit_length() == bits and phi % e:
            d = pow(e, -1, phi)
            break

    ips = []
    for ip in (lan_ip, "127.0.0.1"):
        if ip and ip not in ips:
            ips.append(ip)
    now = datetime.datetime.now(datetime.timezone.utc)
    tbs = _seq(
        _tlv(0xA0, _int(2)),                                  # version v3
        _int(secrets.randbits(63) | 1),                        # serial
        _seq(_OID_SHA256_RSA, _NULL),                          # signature alg
        _name("Apex Live Mocap"),                              # issuer
        _seq(_time(now - datetime.timedelta(days=1)),
             _time(now + datetime.timedelta(days=days))),      # validity
        _name("Apex Live Mocap"),                              # subject
        _seq(_seq(_OID_RSA, _NULL),
             _tlv(0x03, b"\x00" + _seq(_int(n), _int(e)))),    # public key
        _tlv(0xA3, _seq(_seq(_OID_SAN,
                             _tlv(0x04, _general_names(ips, ["localhost"]))))),
    )
    digest = hashlib.sha256(tbs).digest()
    k = (n.bit_length() + 7) // 8
    t = _SHA256_DIGESTINFO + digest
    em = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    signature = pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
    cert_der = _seq(tbs, _seq(_OID_SHA256_RSA, _NULL),
                    _tlv(0x03, b"\x00" + signature))

    key_der = _seq(_int(0), _int(n), _int(e), _int(d), _int(p), _int(q),
                   _int(d % (p - 1)), _int(d % (q - 1)), _int(pow(q, -1, p)))
    return _pem("CERTIFICATE", cert_der), _pem("RSA PRIVATE KEY", key_der), cert_der
