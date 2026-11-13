"""Bounded public HTTP downloads with immutable bodies and verified warm cache."""
from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
import uuid

from .usdm_common import read_json, sha256, utc_now, write_json

HOSTS = {'droughtmonitor.unl.edu','www.droughtmonitor.unl.edu','usdmdataservices.unl.edu'}


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def validate_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username
            or parsed.password or parsed.port not in (None,443)):
        raise ValueError('Downloads must use an approved public UNL HTTPS host')


class HttpCache:
    def __init__(self, folder, resume=True, timeout=60, retries=3, pause=.15, offline=False,
                 opener=None, sleeper=time.sleep):
        self.folder = Path(folder).expanduser().resolve()
        self.resume, self.timeout, self.retries, self.pause = resume,timeout,retries,pause
        self.offline = offline
        self.opener = opener or urllib.request.build_opener(RestrictedRedirect()).open
        self.sleeper = sleeper
        self.network_requests = 0

    def get(self, url, kind, validator, accept=None):
        validate_url(url)
        accept = accept or ('application/json' if kind=='json' else '*/*')
        key = hashlib.sha256((url+'\n'+accept+'\n'+kind).encode()).hexdigest()
        pointer = self.folder/'request_index'/(key+'.json')
        cache_issue = None
        if self.resume and pointer.exists():
            try:
                old = read_json(pointer)
                checksum = str(old['sha256'])
                if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
                    raise ValueError('Invalid cache content hash')
                suffix = {'json':'.json','html':'.html','zip':'.zip'}[kind]
                stored = Path(old['path'])
                path = stored if stored.is_absolute() else self.folder/stored
                # Legacy indexes contain the old absolute root. Recover only the
                # deterministic content-addressed object, never an arbitrary path.
                expected = self.folder/'objects'/checksum[:2]/(checksum+suffix)
                if path.resolve() != expected.resolve():
                    path = expected
                if not path.resolve().is_relative_to(self.folder):
                    raise ValueError('Cache pointer escapes its root')
                if path.stat().st_size != old['bytes'] or sha256(path) != checksum:
                    raise ValueError('Cached body hash/length mismatch')
                if old.get('url') != url or old.get('kind') != kind or old.get('accept') != accept:
                    raise ValueError('Cache request metadata mismatch')
                receipt = Path(old['receipt_path'])
                if not receipt.is_absolute():
                    receipt = self.folder/receipt
                elif not receipt.resolve().is_relative_to(self.folder):
                    receipt = self.folder/'receipts'/key/receipt.name
                if not receipt.resolve().is_relative_to(self.folder/'receipts'/key) or not receipt.is_file():
                    raise ValueError('Original acquisition receipt is unavailable')
                frozen = read_json(receipt)
                if any(frozen.get(k) != old.get(k) for k in ('sha256','bytes','url','retrieved_utc')):
                    raise ValueError('Cache index disagrees with immutable acquisition receipt')
                audit = validator(path)
                current = dict(old, path=path.relative_to(self.folder).as_posix(),
                               receipt_path=receipt.relative_to(self.folder).as_posix())
                if old != current:
                    write_json(pointer,current)
                return dict(current,path=str(path),receipt_path=str(receipt),cache_hit=True,audit=audit)
            except (OSError,ValueError,KeyError) as error:
                cache_issue = str(error)
        if self.offline:
            raise ConnectionError(f'Offline mode has no verified cached response for {url}')
        maximum = 64*1024*1024 if kind=='zip' else 32*1024*1024
        temporary = self.folder/'partial'/(key+'.'+uuid.uuid4().hex+'.part')
        temporary.parent.mkdir(parents=True,exist_ok=True)
        try:
            for attempt in range(self.retries+1):
                try:
                    self.sleeper(self.pause)
                    request = urllib.request.Request(url,headers={
                        'Accept':accept,'User-Agent':'PLAN6059-USDM-audit/1.0'})
                    self.network_requests += 1
                    with self.opener(request,timeout=self.timeout) as response:
                        final_url = response.geturl()
                        validate_url(final_url)
                        if response.status != 200:
                            raise ValueError(f'Unexpected HTTP status {response.status}')
                        size, digest = 0, hashlib.sha256()
                        with temporary.open('wb') as stream:
                            while block := response.read(1024*1024):
                                size += len(block)
                                if size > maximum:
                                    raise ValueError('HTTP body exceeds configured byte limit')
                                digest.update(block)
                                stream.write(block)
                        length = response.headers.get('Content-Length')
                        if length and size != int(length):
                            raise ConnectionError('HTTP body length differs from Content-Length')
                        headers = {k:response.headers.get(k) for k in
                                   ('Content-Type','Last-Modified','ETag')}
                    # A 200 HTML error body is never accepted as JSON or ZIP.
                    if kind=='json':
                        with temporary.open(encoding='utf-8-sig') as stream:
                            if not isinstance(json.load(stream),list):
                                raise ValueError('Statistics response must be a JSON array')
                    elif kind=='zip':
                        with temporary.open('rb') as stream:
                            if stream.read(4) != b'PK\x03\x04':
                                raise ValueError('Archive response lacks ZIP magic')
                    audit = validator(temporary)
                    checksum = digest.hexdigest()
                    suffix = {'json':'.json','html':'.html','zip':'.zip'}[kind]
                    target = self.folder/'objects'/checksum[:2]/(checksum+suffix)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists() and sha256(target) != checksum:
                        quarantine = self.folder/'quarantine'/(target.name+'.'+uuid.uuid4().hex)
                        quarantine.parent.mkdir(parents=True,exist_ok=True)
                        target.replace(quarantine)
                    if not target.exists():
                        temporary.replace(target)
                    receipt = {'url':url,'final_url':final_url,'accept':accept,'kind':kind,
                        'retrieved_utc':utc_now(),'status':200,'bytes':size,'sha256':checksum,
                        'path':str(target),'headers':headers,'attempts':attempt+1}
                    if cache_issue:
                        receipt['repaired_cache_issue'] = cache_issue
                    frozen_receipt = self.folder/'receipts'/key/(uuid.uuid4().hex+'.json')
                    write_json(frozen_receipt,receipt)
                    receipt['receipt_path'] = str(frozen_receipt)
                    write_json(pointer,dict(receipt, path=target.relative_to(self.folder).as_posix(),
                        receipt_path=frozen_receipt.relative_to(self.folder).as_posix()))
                    return dict(receipt,cache_hit=False,audit=audit)
                except urllib.error.HTTPError as error:
                    retry_after = error.headers.get('Retry-After','') if error.headers else ''
                    error.close()
                    if error.code not in (408,429,500,502,503,504) or attempt==self.retries:
                        raise
                    try:
                        delay = min(max(float(retry_after),0),120)
                    except ValueError:
                        delay = min(2**attempt,30)
                    self.sleeper(delay)
                except (urllib.error.URLError,TimeoutError,ConnectionError,http.client.IncompleteRead):
                    if attempt==self.retries:
                        raise
                    self.sleeper(min(2**attempt,30))
        finally:
            if temporary.exists():
                temporary.unlink()

