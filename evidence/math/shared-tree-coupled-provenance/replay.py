from pathlib import Path
import os,subprocess,sys
p=Path(__file__).resolve().parent
env=os.environ.copy();env['PYTHONPATH']=str(p/'dependencies/src');env['OMA_CATALOGUE_CHECK_SOURCE']=str(p/'implementation/src/oma/routing/shared_tree_catalogue_check.py')
tests=[p/'implementation/tests/test_shared_tree_catalogue_check.py',p/'implementation/tests/test_shared_tree_coupled_catalogue_check.py']
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',*map(str,tests),'-q','-o','addopts=','-o','pythonpath='+(p/'dependencies/src').as_posix()],env=env))
