import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from homecoming.settings import ROOT


class SharedConfigurationTests(unittest.TestCase):
    def test_dotenv_is_loaded_without_interpolation_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'src/homecoming/settings.py'
            source.parent.mkdir(parents=True)
            shutil.copyfile(ROOT/'src/homecoming/settings.py',source)
            (root/'.env').write_text('DEEPSEEK_API_KEY="synthetic-${unchanged}"\nDEEPSEEK_MODEL=synthetic-file-model\n')
            environment={k:v for k,v in os.environ.items() if k not in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')}
            environment['PYTHONPATH']=str(root/'src')
            code='import json; from homecoming.settings import DEEPSEEK_API_KEY,MODEL; print(json.dumps([DEEPSEEK_API_KEY,MODEL]))'
            def read():
                return json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=root,env=environment,text=True))
            self.assertEqual(read(),['synthetic-${unchanged}','synthetic-file-model'])
            environment.update(DEEPSEEK_API_KEY='synthetic-environment-key',DEEPSEEK_MODEL='synthetic-env-model')
            self.assertEqual(read(),['synthetic-environment-key','synthetic-env-model'])
            (root/'.env').unlink()
            environment.pop('DEEPSEEK_API_KEY');environment.pop('DEEPSEEK_MODEL')
            self.assertEqual(read(),['','deepseek-flash'])
