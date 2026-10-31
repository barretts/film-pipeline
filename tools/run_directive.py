"""Run one stateful directing directive (CPU dry-plan by default; managed mode renders)."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from local_film import directing

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('plan',help='directive plan.json (experiment format accepted)')
 parser.add_argument('--job',required=True,help='isolated job directory for this directive')
 parser.add_argument('--mode',choices=['dry','managed'],default='dry')
 parser.add_argument('--dry-run',action='store_true',help='alias for --mode dry')
 parser.add_argument('--show-root');parser.add_argument('--show')
 parser.add_argument('--gpu',choices=['off','managed'],help='assert plan gpu mode; refuse contradictions')
 args=parser.parse_args()
 if args.dry_run:args.mode='dry'
 import json
 plan=json.loads(Path(args.plan).read_text(encoding='utf8'))
 if args.gpu:
  effective=plan.get('gpu','managed')
  if args.gpu!=effective:raise SystemExit(f'refusing: --gpu {args.gpu} contradicts plan gpu={effective}')
 if args.mode=='managed' and plan.get('gpu','managed')!='managed':raise SystemExit('refusing: plan pins gpu=off; managed rendering requires gpu=managed')
 result=directing.run_directive(args.plan,args.job,mode=args.mode,show_root=args.show_root,show_name=args.show)
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
