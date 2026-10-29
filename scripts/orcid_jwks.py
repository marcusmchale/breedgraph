#!/usr/bin/env python3
"""
Refresh the keys ORCID signs id_tokens with, which BreedGraph packages so that the API checks ORCID sign-in without
contacting ORCID (docs/person.md, ORCID). Writes ORCID's and the sandbox's key sets to src/breedgraph/adapters/orcid/jwks/,
as ORCID publishes them at <ORCID_BASE_URL>/oauth/jwks. Run it on a machine that reaches orcid.org, not the server, before
each release (docs/releasing.md): git diff then shows whether ORCID has changed a key.

A server can take a changed key before a release carries it: write the set to a file there and name it in
ORCID_JWKS_PATH (docs/deployment.md, ORCID linking).

Usage:  python scripts/orcid_jwks.py [--output <directory>]
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

HOSTS = ['orcid.org', 'sandbox.orcid.org']
PACKAGED = Path(__file__).parent.parent / 'src' / 'breedgraph' / 'adapters' / 'orcid' / 'jwks'


def fetch(host: str) -> dict:
    request = Request(f"https://{host}/oauth/jwks", headers={'Accept': 'application/json'})
    with urlopen(request, timeout=20) as response:
        jwks = json.load(response)
    if not [key for key in jwks.get('keys', []) if key.get('kty') == 'RSA' and key.get('kid')]:
        raise SystemExit(f"{host} returned no RSA keys with ids: {jwks}")
    return jwks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=PACKAGED, help="where to write the key sets")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for host in HOSTS:
        jwks = fetch(host)
        path = args.output / f"{host}.json"
        path.write_text(json.dumps(jwks, indent=2) + '\n')
        print(f"{path}: {', '.join(key['kid'] for key in jwks['keys'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
