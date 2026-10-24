"""Mutants for rebuild.test.mjs.

Each mutant undoes one fix in BOTH the draft body and replacements.json, so
the ledger check cannot be what kills it; a behaviour test has to. Preflight
carries byte copies of some OS 28 and Doctor Gate lines, so a mutant of a
copied line is applied to the Preflight copy too; otherwise the drift check
alone would kill it and prove nothing about behaviour. It works on a temporary
copy of this folder and never edits the real files.

    python3 n8n/tqo-v5/compliance/rebuild/mutants.py

Exits 0 only when every mutant is killed and every mutant applies exactly once.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIRROR = "Preflight: Can This Clear?"
FILES = {
    "OS 28: Publish Gate": "os28_publish_gate.js",
    "Script: Fill Run Fields": "fill_run_fields.js",
    "QC Doctor Gate": "qc_doctor_gate.js",
    "Preflight: Can This Clear?": "preflight_can_this_clear.js",
}

# (name, node, [(old, new), ...]). Each old text must occur once in the draft.
MUTANTS = [
    ("tension word without the leading boundary", "OS 28: Publish Gate",
     [(r"/\b(?:stop|", r"/(?:stop|")]),
    ("tension word without inflections", "OS 28: Publish Gate",
     [("(?:s|es|d|ed|ped|ping|ing|ly|en|ful)?\\b/i", "\\b/i")]),
    ("a general er ending lets Coster pass", "OS 28: Publish Gate",
     [("(?:s|es|d|ed|ped|ping|ing|ly|en|ful)?\\b/i", "(?:s|es|d|ed|ped|ping|ing|ly|er|en|ful)?\\b/i")]),
    ("mistaken no longer a tension word", "OS 28: Publish Gate",
     [("|mistaken|", "|")]),
    ("OS 28 lets Not required pass", "OS 28: Publish Gate",
     [("const PLACED = ['Disclosed in description', 'Disclosed on-screen + description'];",
       "const PLACED = ['Disclosed in description', 'Disclosed on-screen + description', 'Not required'];"),
      ("if (disc === 'Not required') {", "if (false) {")]),
    ("C4 line anywhere in the description", "OS 28: Publish Gate",
     [("gates.c4_disclosure = descHead.some(l => l.trim() === C4_LINE);",
       "gates.c4_disclosure = descText.includes(C4_LINE);")]),
    ("dash check dropped", "OS 28: Publish Gate",
     [("if (DASH.test(title)) lawTitle.push", "if (false) lawTitle.push")]),
    ("proper noun check dropped", "OS 28: Publish Gate",
     [("if (title && !properNoun.test(title)) lawTitle.push", "if (false) lawTitle.push")]),
    ("fill keeps a looser phrase", "Script: Fill Run Fields",
     [("desc = (DISCLOSURE + '\\n\\n' + desc.split(DISCLOSURE).join('').trim()).trim();",
       "if (!/AI-assisted/i.test(desc)) desc = (DISCLOSURE + '\\n\\n' + desc.split(DISCLOSURE).join('').trim()).trim();")]),
    ("doctor verdict is its first word", "QC Doctor Gate",
     [("\\s+([^|\\n]*?)\\s*(?=\\||\\n|$)/g", "\\s+([A-Z_]+)(?=\\s|\\||$)/gi")]),
    ("doctor entry needs no bar", "QC Doctor Gate",
     [("matchAll(/\\|\\s*doctor", "matchAll(/\\s*doctor")]),
    ("doctor score drops decimals", "QC Doctor Gate",
     [("(\\d+(?:\\.\\d+)?)\\/100", "(\\d+)\\/100")]),
    ("doctor floor 70", "QC Doctor Gate",
     [("const DOCTOR_FLOOR = 90;", "const DOCTOR_FLOOR = 70;")]),
    ("oldest doctor line counts", "QC Doctor Gate",
     [("doctorLines[doctorLines.length - 1]", "doctorLines[0]")]),
    ("doctor verdict ignored", "QC Doctor Gate",
     [("presenterDoctorVerdict: scriptClear ? doctorVerdict : 'UNCHECKED',",
       "presenterDoctorVerdict: (verdict === 'SHIP' ? 'REPAIRED' : 'UNCHECKED'),")]),
    ("doctor score ignored", "QC Doctor Gate",
     [("&& doctorScore >= DOCTOR_FLOOR;", ";")]),
    ("preflight mirror skips the C4 placement", "Preflight: Can This Clear?",
     [("if (!desc.split('\\n').slice(0, 3).some(l => l.trim() === C4_LINE)) blockers.push",
       "if (false) blockers.push")]),
    ("preflight mirror skips law 6", "Preflight: Can This Clear?",
     [("if (title && !tensionWord.test(title)) blockers.push", "if (false) blockers.push")]),
    ("preflight mirror skips the doctor rule", "Preflight: Can This Clear?",
     [("if (!(['PASS', 'REPAIRED'].includes(doctorVerdict) && doctorScore >= DOCTOR_FLOOR)) {",
       "if (false) {")]),
    ("preflight C4 compare without trim", "Preflight: Can This Clear?",
     [("slice(0, 3).some(l => l.trim() === C4_LINE)) blockers.push", "slice(0, 3).some(l => l === C4_LINE)) blockers.push")]),
    ("preflight C4 check on the untrimmed description", "Preflight: Can This Clear?",
     [("if (!desc.split('\\n').slice(0, 3)", "if (!String(f.Description ?? '').split('\\n').slice(0, 3)")]),
    ("preflight C4 line may carry trailing text", "Preflight: Can This Clear?",
     [("some(l => l.trim() === C4_LINE)) blockers.push", "some(l => l.trim().startsWith(C4_LINE))) blockers.push")]),
    ("preflight copy drifts from the Doctor Gate", "Preflight: Can This Clear?",
     [("const DOCTOR_FLOOR = 90;", "const DOCTOR_FLOOR = 85;")]),
    ("preflight accepts Not required", "Preflight: Can This Clear?",
     [("if (disc === 'Not required') {", "if (false) {"),
      ("} else if (!['Disclosed in description', 'Disclosed on-screen + description'].includes(disc)) {",
       "} else if (!['Not required', 'Disclosed in description', 'Disclosed on-screen + description'].includes(disc)) {")]),
]


def run(folder):
    return subprocess.run(["node", str(folder / "rebuild.test.mjs")], capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp())
    ok = True
    try:
        control = tmp / "control"
        shutil.copytree(HERE, control)
        if run(control).returncode != 0:
            print("CONTROL FAILED: the unmutated test does not pass")
            return 1
        for name, node, steps in MUTANTS:
            work = tmp / "work"
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(HERE, work)
            ledger = json.loads((work / "replacements.json").read_text())
            codes = {n: (work / "draft" / f).read_text() for n, f in FILES.items()}
            applied = True
            for old, new in steps:
                hits = sum(pair[1].count(old) for pair in ledger[node])
                if hits != 1 or codes[node].count(old) != 1:
                    print("BAD MUTANT", name, "ledger hits", hits, "draft hits", codes[node].count(old))
                    applied = False
                    break
                targets = [node]
                if node != MIRROR and codes[MIRROR].count(old) == 1:
                    targets.append(MIRROR)
                for target in targets:
                    for pair in ledger[target]:
                        pair[1] = pair[1].replace(old, new)
                    codes[target] = codes[target].replace(old, new)
            if not applied:
                ok = False
                continue
            (work / "replacements.json").write_text(json.dumps(ledger, indent=2))
            for n, f in FILES.items():
                (work / "draft" / f).write_text(codes[n])
            result = run(work)
            by_ledger = "listed replacements" in result.stderr or "occurs once" in result.stderr
            by_drift = "Preflight copies" in result.stderr
            killed = result.returncode != 0 and not by_ledger and (node == MIRROR or not by_drift)
            ok = ok and killed
            first = next((line.strip() for line in result.stderr.splitlines() if "AssertionError" in line), "")
            print(("KILLED   " if killed else "SURVIVED ") + name + " | " + first[:140])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL KILLED" if ok else "SOME SURVIVED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
