# Deployment Notes

本文档记录课程交付使用的 Docker 分发与公网 WebUI 部署方式。项目的首选分发形态是
Docker/OCI 镜像；当公开 registry 登录或推送不可用时，使用本地 `docker save` 与服务器
`docker load` 传输同一镜像。

## Server

- Server IP: `120.27.140.93`
- Public URL: `http://120.27.140.93/`
- Open port: `80`
- Container image tag: `coding-agent-harness:5af067b`
- Image transfer method: local `docker save`, server `docker load`
- Runtime workspace: `/srv/coding-agent-harness/workspace`
- Runtime state: `/srv/coding-agent-harness/workspace/.harness/`

The WebUI is a minimal FastAPI status and approval adapter. It does not execute
shell commands directly and uses the same JSON runtime state as the CLI.

## Prerequisites

Local machine:

- Docker daemon available.
- Repository checkout at the project root.
- SSH/SCP, WinSCP, Xftp, or another file transfer tool for uploading the image archive.

Server:

- Linux host reachable at `120.27.140.93`.
- Port `80` open to inbound HTTP traffic.
- A user account with permission to install Docker or run Docker commands through `sudo`.

## Local Packaging

Build or reuse the local image, then export it as a tar archive:

```powershell
docker build -t coding-agent-harness:5af067b .
docker save coding-agent-harness:5af067b -o coding-agent-harness-5af067b.tar
```

Do not commit `coding-agent-harness-5af067b.tar`; it is a generated distribution artifact.

Transfer the archive to the server:

```powershell
scp .\coding-agent-harness-5af067b.tar 用户名@120.27.140.93:/tmp/
```

If `scp` is unavailable, upload `coding-agent-harness-5af067b.tar` to
`/tmp/coding-agent-harness-5af067b.tar` with WinSCP, Xftp, or the server
provider's file manager.

## Server Deployment

Install and start Docker if it is not already available:

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
```

Load the transferred image:

```bash
docker load -i /tmp/coding-agent-harness-5af067b.tar
docker images | grep coding-agent-harness
```

Start the WebUI on port 80. The container still listens on port 8000
internally, so the host mapping is `80:8000`:

```bash
sudo mkdir -p /srv/coding-agent-harness/workspace

docker run -d \
  --name coding-agent-harness \
  --restart unless-stopped \
  -p 80:8000 \
  -v /srv/coding-agent-harness/workspace:/workspace \
  coding-agent-harness:5af067b \
  uvicorn harness.web:app --host 0.0.0.0 --port 8000 --proxy-headers
```

## Verification

Check the container and HTTP endpoint:

```bash
docker ps
docker logs --tail 100 coding-agent-harness
curl -f http://127.0.0.1/
```

From a browser, open:

```text
http://120.27.140.93/
```

## Restart And Update

Restart the current deployment:

```bash
docker restart coding-agent-harness
```

Replace the running container after loading a newer image:

```bash
docker stop coding-agent-harness
docker rm coding-agent-harness

docker run -d \
  --name coding-agent-harness \
  --restart unless-stopped \
  -p 80:8000 \
  -v /srv/coding-agent-harness/workspace:/workspace \
  coding-agent-harness:5af067b \
  uvicorn harness.web:app --host 0.0.0.0 --port 8000 --proxy-headers
```

The persistent runtime state is stored under:

```text
/srv/coding-agent-harness/workspace/.harness/
```

## Rollback

If a newer image fails after deployment, stop and remove the failed container,
then run the previous known-good tag again:

```bash
docker stop coding-agent-harness
docker rm coding-agent-harness

docker run -d \
  --name coding-agent-harness \
  --restart unless-stopped \
  -p 80:8000 \
  -v /srv/coding-agent-harness/workspace:/workspace \
  coding-agent-harness:5af067b \
  uvicorn harness.web:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Because `.harness/` is stored in the mounted workspace, restarting or replacing
the container preserves approvals, memory, runs, and logs.

## Security Notes

- Do not upload `.env`, API keys, SSH private keys, or provider tokens with the project.
- Real LLM credentials should be configured on the target machine through `harness credentials set`
  or through a controlled `OPENAI_API_KEY` environment variable.
- The WebUI should be treated as an internal demonstration endpoint. It is intentionally minimal and
  does not add authentication, TLS termination, or a multi-user permission model.
- Shell execution remains governed by the harness risk classifier, path fence, finite command timeout,
  and HITL approval state machine.
