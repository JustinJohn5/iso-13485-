"""隔离 E2E 专用 STARTTLS SMTP 收件箱；不会向外网转发邮件。"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
import re
import socketserver
import ssl
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


class MailSink:
    def __init__(self, host: str, port: int, directory: Path, username: str, password: str, prefix: str):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("测试收件箱只允许监听回环地址")
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        self.cert_path = directory / "ca.pem"
        key_path = directory / "key.pem"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ISO E2E Mail")])
        instant = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(instant - timedelta(minutes=1))
                .not_valid_after(instant + timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([
                    x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))
                ]), critical=False).sign(key, hashes.SHA256()))
        self.cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_path, key_path)
        expected_auth = base64.b64encode(f"\0{username}\0{password}".encode()).decode()
        sink = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(15)
                self.wfile.write(b"220 localhost ISO E2E SMTP\r\n")
                tls = False
                authenticated = False
                recipients = []
                while line := self.rfile.readline(8192):
                    command = line.decode("ascii", errors="replace").strip()
                    verb = command.split(" ", 1)[0].upper()
                    if verb in {"EHLO", "HELO"}:
                        self.wfile.write(b"250-localhost\r\n250-AUTH PLAIN\r\n250 STARTTLS\r\n")
                    elif verb == "STARTTLS" and not tls:
                        self.wfile.write(b"220 Ready\r\n")
                        self.connection = context.wrap_socket(self.connection, server_side=True)
                        self.rfile = self.connection.makefile("rb")
                        self.wfile = self.connection.makefile("wb", buffering=0)
                        tls = True
                    elif verb == "AUTH":
                        authenticated = tls and command == f"AUTH PLAIN {expected_auth}"
                        self.wfile.write(b"235 Authenticated\r\n" if authenticated else b"535 Rejected\r\n")
                    elif verb == "MAIL" and authenticated:
                        recipients = []
                        self.wfile.write(b"250 OK\r\n")
                    elif verb == "RCPT" and authenticated:
                        address = command.split(":", 1)[-1].strip("<> ").lower()
                        if not address.startswith(prefix + "-") or not address.endswith("@example.com"):
                            self.wfile.write(b"550 Only test recipients\r\n")
                            continue
                        recipients.append(address)
                        self.wfile.write(b"250 OK\r\n")
                    elif verb == "DATA" and authenticated and recipients:
                        self.wfile.write(b"354 End with dot\r\n")
                        body = bytearray()
                        while data := self.rfile.readline(8192):
                            if data == b".\r\n":
                                break
                            body.extend(data[1:] if data.startswith(b"..") else data)
                        message = BytesParser(policy=policy.default).parsebytes(bytes(body))
                        content = message.get_content()
                        match = re.search(r"(?<![0-9])([0-9]{6})(?![0-9])", content)
                        if not match:
                            self.wfile.write(b"550 Missing verification code\r\n")
                            continue
                        for address in recipients:
                            name = hashlib.sha256(address.encode()).hexdigest() + ".json"
                            (sink.directory / name).write_text(
                                json.dumps({"email": address, "code": match.group(1)}), encoding="utf-8")
                        self.wfile.write(b"250 Queued\r\n")
                    elif verb == "QUIT":
                        self.wfile.write(b"221 Bye\r\n")
                        break
                    elif verb in {"RSET", "NOOP"}:
                        self.wfile.write(b"250 OK\r\n")
                    else:
                        self.wfile.write(b"530 Authentication required\r\n")

        self.server = socketserver.ThreadingTCPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
