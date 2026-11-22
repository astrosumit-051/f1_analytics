"""Reproduce synthetic regression checks; never run a historical model or holdout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rscript",help="Optional Rscript executable with shiny installed")
    a=p.parse_args();checks=[]
    commands=[("contracts",[sys.executable,"contracts/check_contract.py","--fake"]),
        ("python_regressions",[sys.executable,"-m","pytest","evaluation","figures","analysis/extensions","-q"])]
    if a.rscript:commands.append(("shiny_regressions",[a.rscript,"--vanilla","demo/test_app.R"]))
    for name,argv in commands:
        started=time.monotonic()
        run=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=240)
        checks.append(dict(check=name,returncode=run.returncode,elapsed_sec=time.monotonic()-started,
            stdout=run.stdout,stderr=run.stderr,
            assertion_marker="ALL SHINY CHECKS PASSED" in run.stdout if name=="shiny_regressions" else None,
            process_passed=run.returncode==0))
        print(f"{name}: exit {run.returncode}")
    out=ROOT/"evaluation/results";out.mkdir(parents=True,exist_ok=True)
    report=dict(checks=checks,r_checked=bool(a.rscript),production_integration="pending model and shared approvals",
        protected_evaluation="not run")
    (out/"validation_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return 0 if all(c["process_passed"] for c in checks) else 1


if __name__=="__main__":sys.exit(main())
