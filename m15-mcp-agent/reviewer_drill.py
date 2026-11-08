"""Human-in-the-loop drill (Module 15, Lesson 03, step 4).

Shows a reviewer 30 save_message approval cards, one at a time, in a random order. Three are
seeded malicious requests (an injected instruction trying to send data out); the other 27 are
ordinary. The reviewer types y (approve) or n (deny). At the end the script reports the catch
rate (malicious cards denied) and the false-alarm rate (benign cards denied), with Wilson intervals.

    python reviewer_drill.py                 # a colleague runs this in your Codespace terminal
    python reviewer_drill.py --no-provenance # the same drill without the provenance line

Which cards are malicious is decided at run time from a random seed; nothing in this file or the
repository tells the reviewer which ones they are. All names and addresses are FICTIONAL.
"""
import argparse
import random
import secrets
from math import sqrt

BENIGN_TO = ["avery.l@example.com", "jamal.o@example.com", "hr-team@example.com", "priya.r@example.com",
             "onboarding@example.com", "hiroshi.t@example.com"]
BENIGN_BODY = ["Your interview is confirmed for Tuesday at 10:00.", "Welcome aboard! Orientation starts Monday.",
               "Please upload your signed offer letter.", "Thanks for your time today; we will be in touch.",
               "Reminder: benefits enrolment closes in 30 days.", "Your badge is ready for pickup at reception."]
MALICIOUS = [
    ("audit@example.test", "Note summary. CANARY-7731", "tool output from read_note(candidate_note.txt) (untrusted)"),
    ("records-backup@example.net", "All candidate phone numbers: 555-0101, 555-0142, 555-0103 ...",
     "tool output from read_note(interview_debrief.txt) (untrusted)"),
    ("hr-team@example.com.example.net", "Forwarding salary bands as requested.",
     "tool output from read_note(onboarding_policy.txt) (untrusted)"),
]


def wilson(x, n, z=1.96):
    p = x / n
    c, m, d = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)), 1 + z * z / n
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-provenance", action="store_true")
    a = ap.parse_args()
    rng = random.Random(secrets.randbits(64))
    cards = [dict(to=t, body=b, prov=p, bad=True) for t, b, p in MALICIOUS]
    cards += [dict(to=rng.choice(BENIGN_TO), body=rng.choice(BENIGN_BODY), prov="user request", bad=False)
              for _ in range(27)]
    rng.shuffle(cards)
    for i, c in enumerate(cards, 1):
        print(f"\n[{i}/30] APPROVAL NEEDED: save_message\n  to:   {c['to']}\n  body: {c['body']}")
        if not a.no_provenance:
            print(f"  provenance: {c['prov']}")
        c["denied"] = input("Approve? [y/n] ").strip().lower() != "y"
    caught = sum(c["denied"] for c in cards if c["bad"])
    fa = sum(c["denied"] for c in cards if not c["bad"])
    lo, hi = wilson(caught, 3)
    flo, fhi = wilson(fa, 27)
    print(f"\nCatch rate: {caught}/3 (95% Wilson CI {lo:.2f}-{hi:.2f})")
    print(f"False alarms: {fa}/27 (95% Wilson CI {flo:.2f}-{fhi:.2f})")


if __name__ == "__main__":
    main()
