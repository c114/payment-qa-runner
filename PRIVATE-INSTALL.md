# Private Repository 安装（推荐）

当前仓库默认 **PRIVATE**，VPS 不能匿名拉取。

## 前提

- Ubuntu 22.04 / 24.04 或 Debian 12 / 13
- 能访问 GitHub
- sudo 权限

## 步骤

### 1. 安装 git 与 GitHub CLI

```bash
sudo apt-get update
sudo apt-get install -y curl git
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt-get update
sudo apt-get install -y gh
```

### 2. 登录 GitHub（网页授权）

```bash
gh auth login --web
```

在浏览器完成登录 / 2FA。

### 3. Clone 并安装

```bash
gh repo clone c114/payment-qa-runner /opt/payment-qa-runner && \
cd /opt/payment-qa-runner && \
sudo bash install.sh
```

`install.sh` 会安装 Docker（如需要）、生成密钥、构建并启动容器。

首次安装结束时终端会显示临时管理员密码（仅显示一次，不会写入 GitHub）。

### 4. 打开面板

```
http://SERVER_IP:3000
```

API：`http://SERVER_IP:8000`

## 日常命令

```bash
cd /opt/payment-qa-runner
sudo bash update.sh
sudo bash status.sh
sudo bash logs.sh
sudo bash restart.sh
sudo bash backup.sh
```

## 不要做的事

- 不要为了“一键 curl raw”而把仓库改成 Public（除非你主动决定）
- 不要把 `.env`、密码、备份包提交到 Git
