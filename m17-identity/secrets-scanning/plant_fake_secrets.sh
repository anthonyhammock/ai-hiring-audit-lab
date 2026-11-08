#!/usr/bin/env bash
# Plant FAKE, NON-WORKING secrets in a throwaway test repository (Module 17, Lesson 03, step 1).
#
#   bash plant_fake_secrets.sh /path/to/your/test-repo
#
# Run it only in a repository you own and created for this exercise (for example your public
# fork of this lab repository, or a new repository). The values are random strings generated on
# your machine: they do not work anywhere. They are built at run time so that this lab repository
# itself contains no secret-shaped strings.
set -euo pipefail
repo="${1:?usage: plant_fake_secrets.sh /path/to/test-repo}"
cd "$repo"
git rev-parse --git-dir >/dev/null
rand() { python3 -c "import secrets,string;print(''.join(secrets.choice('$1') for _ in range($2)))"; }
mkdir -p hr-analytics
lab_key="blk_live_$(rand 0123456789abcdef 32)"
api_key="$(rand ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 40)"
cat > hr-analytics/settings.py <<PY
# FICTIONAL people-analytics app settings (lab exercise; these values are fake and do not work)
SURVEY_EXPORT_BUCKET = "survey-exports-lab"
BLISSLAB_KEY = "${lab_key}"
summariser_api_key = "${api_key}"
PY
git add hr-analytics/settings.py
git commit -q -m "Add analytics settings (lab exercise: contains planted fake secrets)"
echo "Planted two fake secrets in hr-analytics/settings.py and committed them:"
git log --oneline -1
