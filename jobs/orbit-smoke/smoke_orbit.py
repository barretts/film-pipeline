import shutil,sys
from pathlib import Path
sys.path.insert(0,'F:/film-pipeline/tools');sys.path.insert(0,'F:/film-pipeline')
import create_character as cc
tmp=Path('F:/film-pipeline/jobs/scratch-orbit');shutil.rmtree(tmp,ignore_errors=True);(tmp/'refs').mkdir(parents=True)
shutil.copy2('F:/film-pipeline/series/characters/kate/portrait-candidate-1.png',tmp/'portrait.png')
refs,mode=cc.orbit_refs(tmp,tmp/'portrait.png')
print('refs:',refs,'mode:',mode)
