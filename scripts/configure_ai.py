"""Enter the shared DeepSeek key privately and save it in the app's .env."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from homecoming.services.deepseek import ProviderError,validate_key


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-validation',action='store_true',help='Save without contacting the models endpoint.')
    args=parser.parse_args()
    key=getpass.getpass('DeepSeek API key (hidden): ').strip()
    if not key or any(ord(c)<33 or ord(c)>126 for c in key):
        raise SystemExit('Enter a nonempty API key without spaces or control characters. Nothing was changed.')
    if not args.skip_validation:
        try:
            asyncio.run(validate_key(key))
        except ProviderError as exc:
            raise SystemExit(str(exc)+' Nothing was changed.')
    path=ROOT/'.env'
    lines=path.read_text().splitlines() if path.exists() else (ROOT/'.env.example').read_text().splitlines()
    replacement='DEEPSEEK_API_KEY='+json.dumps(key)
    output=[];found=False
    for line in lines:
        if re.match(r'^\s*(?:export\s+)?DEEPSEEK_API_KEY\s*=',line):
            if not found:output.append(replacement)
            found=True
        else:output.append(line)
    if not found:output.append(replacement)
    descriptor,temporary=tempfile.mkstemp(prefix='.env-',dir=ROOT)
    try:
        with os.fdopen(descriptor,'w') as stream:
            stream.write('\n'.join(output)+'\n')
        os.chmod(temporary,0o600)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    print('Saved the server API key in .env with owner-only permissions.')
    print('On the VPS, run: systemctl restart homecoming')


if __name__=='__main__':main()
