# Secrets scanning with gitleaks (Module 17, Lesson 03, step 1)

> **FAKE SECRETS ONLY.** The script generates random, non-working strings. Plant them only in a repository you own and made for this exercise. Never scan, clone or report on repositories you do not own.

**Why a public fork?** GitHub secret scanning on *private* repositories needs a paid licence (GitHub Secret Protection / Advanced Security). It runs at no cost on *public* repositories. So this exercise uses a **public repository you own**: either your fork of this lab repository, or a new empty public repository. The fake secrets are random and useless, so publishing them is harmless, and the exercise teaches you why real secrets must never reach a public repository in the first place.

Note what each tool can see:
- **gitleaks** (open source, MIT) uses its built-in rules plus the custom rule in `.gitleaks.toml`, which matches the lab's fake key format `blk_live_` + 32 hex characters.
- **GitHub secret scanning** alerts on the provider token formats GitHub supports. It will not know the lab's made-up format, and custom patterns are not available on a personal public repository. Expect gitleaks to find more here than GitHub does, and record that difference: it is a finding about coverage.

## Steps (in a Codespace)

1. **Fork** this repository to your own account on GitHub (or create a new public repository) and open **your fork** in a Codespace. Optionally, turn on secret scanning in your fork's **Settings → Advanced Security** (on a fork you may need to enable it explicitly).
2. **Install gitleaks** (v8.30.1 was the latest release on 2026-11-07). In the Codespace terminal:
   ```bash
   cd /tmp && curl -sSLO https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
   tar -xzf gitleaks_8.30.1_linux_x64.tar.gz gitleaks && sudo mv gitleaks /usr/local/bin/ && gitleaks version
   ```
   (Check the release page for the current version and its published checksums file before you install.)
3. **Plant** the fake secrets in a new branch of your fork:
   ```bash
   cd /workspaces/<your-fork>
   git switch -c secrets-exercise
   bash m17-identity/secrets-scanning/plant_fake_secrets.sh .
   ```
4. **Find** them, in history as well as the working tree:
   ```bash
   gitleaks git -c m17-identity/secrets-scanning/.gitleaks.toml --redact -v .
   gitleaks dir -c m17-identity/secrets-scanning/.gitleaks.toml --redact -v hr-analytics
   ```
   Expect two findings: `generic-api-key` and `blisspoint-lab-key`.
5. *(Optional, GitHub detection.)* Push the branch to your public fork: `git push -u origin secrets-exercise`. Check the **Security** tab for alerts and record what GitHub did and did not detect.
6. **Remove** the file from history. In a real incident you would first **revoke and rotate** the key: removal does not undo exposure.
   ```bash
   pip install git-filter-repo==2.47.0
   git filter-repo --force --invert-paths --path hr-analytics/settings.py --refs secrets-exercise
   gitleaks git -c m17-identity/secrets-scanning/.gitleaks.toml --redact .    # expect: no leaks found
   ```
   `git filter-repo` removes the `origin` remote as a safety measure. If you pushed in step 5, add it back (`git remote add origin <your fork URL>`), force-push the rewritten branch, and note that copies may remain in other clones, forks and caches.
7. **Prevent:** add gitleaks as a pre-commit check (`gitleaks git --pre-commit --staged`) and write down what it would and would not have stopped.

**Colab route:** the same commands work in a Colab terminal or `!` cells on a fresh `git init` repository, but steps 1 and 5 (GitHub's own scanning) need the Codespace and your fork.
