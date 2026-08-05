import hashlib
import io
import shlex
import socket
import time

import paramiko

from .security import decrypt_secret


def fingerprint(key):
    digest = hashlib.sha256(key.asbytes()).digest()
    import base64
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def connect(server, trust_new=False):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    secret = decrypt_secret(server["secret_encrypted"])
    options = dict(
        hostname=server["host"], port=server["port"], username=server["username"],
        timeout=10, banner_timeout=10, auth_timeout=10, look_for_keys=False, allow_agent=False,
    )
    if server["auth_type"] == "password":
        options["password"] = secret
    else:
        passphrase = decrypt_secret(server["key_passphrase_encrypted"]) if server["key_passphrase_encrypted"] else None
        last_error = None
        for key_type in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                options["pkey"] = key_type.from_private_key(io.StringIO(secret), password=passphrase)
                break
            except (paramiko.SSHException, ValueError) as exc:
                last_error = exc
        else:
            raise RuntimeError("无法解析 SSH 私钥") from last_error
    client.connect(**options)
    actual = fingerprint(client.get_transport().get_remote_server_key())
    expected = server["host_fingerprint"]
    if expected and expected != actual:
        client.close()
        raise RuntimeError(f"服务器指纹已变化（当前 {actual}），已拒绝连接")
    if not expected and not trust_new:
        client.close()
        raise RuntimeError(f"服务器指纹尚未确认：{actual}")
    return client, actual


def test_server(server):
    client, actual = connect(server, trust_new=True)
    try:
        _, stdout, stderr = client.exec_command("docker version --format '{{.Server.Version}}'", timeout=15)
        code = stdout.channel.recv_exit_status()
        detail = (stdout.read() + stderr.read()).decode("utf-8", "replace").strip()
        if code != 0:
            raise RuntimeError("Docker 权限检查失败：" + detail[:300])
        return actual, detail
    finally:
        client.close()


def export_logs(server, container, start, end, output_file, timeout=1800):
    client, _ = connect(server)
    command = "docker logs --timestamps --since {} --until {} {} 2>&1".format(
        shlex.quote(start), shlex.quote(end), shlex.quote(container)
    )
    try:
        _, stdout, _ = client.exec_command(command, timeout=15)
        channel = stdout.channel
        channel.settimeout(15)
        with open(output_file, "wb") as target:
            deadline = time.monotonic() + timeout
            while True:
                if time.monotonic() >= deadline:
                    channel.close()
                    raise RuntimeError("日志导出超过最大执行时间")
                try:
                    chunk = channel.recv(65536)
                except socket.timeout:
                    if channel.exit_status_ready():
                        break
                    continue
                if not chunk:
                    break
                target.write(chunk)
        code = channel.recv_exit_status()
        if code != 0:
            raise RuntimeError(f"docker logs 执行失败，退出码 {code}")
    finally:
        client.close()
