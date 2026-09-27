# Install notes

Repository is **PUBLIC**: https://github.com/c114/payment-qa-runner

Preferred:

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
```

or:

```bash
git clone https://github.com/c114/payment-qa-runner.git /opt/payment-qa-runner
cd /opt/payment-qa-runner && sudo bash install.sh
```

If the repo is ever made private again, use `gh auth login` + `gh repo clone c114/payment-qa-runner`.

Same-Origin (1.3.0): open only `http://SERVER:3000` — no manual `NEXT_PUBLIC_API_URL` / CORS IP edits.
