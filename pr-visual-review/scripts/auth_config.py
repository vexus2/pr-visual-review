#!/usr/bin/env python3
"""Validate a PR visual review login recipe without reading credentials or logging in.

Python 3.10+, standard library only. Output is a fixed-field summary; free text,
credential references and configuration contents are never echoed.
"""
import argparse
import json
from pathlib import Path
import re
import sys

MODES = ('existing-session', 'form', 'manual', 'fixture', 'none')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys_only(obj, allowed):
    require(isinstance(obj, dict) and set(obj).issubset(allowed), 'Unknown or disallowed configuration field')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def local_path(value):
    return nonempty(value) and '://' not in value and not any(ord(c) < 32 for c in value)


def route(value):
    # Relative to each verified local app origin; never a redirect/credential URL.
    return (nonempty(value) and value.startswith('/') and not value.startswith('//')
            and not any(c in value for c in ('?', '#', '\\', '%'))
            and not any(c.isspace() or ord(c) < 32 for c in value))


def validate(config):
    keys_only(config, {'schema_version', 'auth'})
    require(type(config.get('schema_version')) is int and config['schema_version'] == 1,
            'Configuration schema_version must be 1')
    recipe = config.get('auth')
    keys_only(recipe, {'mode', 'login_path', 'target_path', 'account_label', 'required_role',
                       'steps', 'success_checks', 'credentials', 'guide'})
    mode = recipe.get('mode')
    require(mode in MODES, 'Unsupported auth mode')
    require(route(recipe.get('target_path')), 'target_path must be a local route without query or fragment')
    if 'login_path' in recipe:
        require(route(recipe['login_path']), 'login_path must be a local route without query or fragment')
    if mode in ('form', 'manual'):
        require('login_path' in recipe, 'Selected mode requires login_path')
    for field in ('steps', 'success_checks'):
        value = recipe.get(field)
        require(isinstance(value, list) and bool(value) and all(nonempty(item) for item in value),
                'steps and success_checks must contain non-empty text')
    if mode != 'none':
        require(nonempty(recipe.get('account_label')) and nonempty(recipe.get('required_role')),
                'Authenticated modes require account_label and required_role')
    if 'guide' in recipe:
        require(local_path(recipe['guide']), 'guide must be a local document path')
    if mode == 'fixture':
        require('guide' in recipe, 'Fixture mode requires a local guide')
    source = 'none'
    if mode == 'form':
        creds = recipe.get('credentials')
        require(isinstance(creds, dict), 'Form mode requires credential references')
        source = creds.get('source')
        if source == 'env':
            keys_only(creds, {'source', 'username', 'password'})
            require(all(isinstance(creds.get(k), str) and re.fullmatch(r'[A-Z_][A-Z0-9_]*', creds[k])
                        for k in ('username', 'password')), 'Credentials must reference environment variable names')
        elif source == 'local-file':
            keys_only(creds, {'source', 'path', 'username_key', 'password_key'})
            require(local_path(creds.get('path')), 'Credentials must reference a local JSON file')
            require(all(nonempty(creds.get(k)) for k in ('username_key', 'password_key')),
                    'Credential JSON keys required')
        else:
            raise ValueError('Unsupported credential reference source')
    else:
        require('credentials' not in recipe, 'Remove credential references when changing away from form mode')
    return {'valid': True, 'mode': mode, 'credentials_source': source,
            'step_count': len(recipe['steps']), 'success_check_count': len(recipe['success_checks'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        print(json.dumps(validate(config), ensure_ascii=False))
    except (OSError, UnicodeError, json.JSONDecodeError):
        print('auth-config: cannot read valid UTF-8 JSON configuration', file=sys.stderr)
        return 1
    except (ValueError, TypeError):
        # Schema errors may originate from arbitrary input. Never echo values.
        print('auth-config: invalid recipe; check authentication.md for allowed fields and modes', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
