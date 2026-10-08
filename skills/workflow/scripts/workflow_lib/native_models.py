"""Supported native host transports. No credentials, model catalog scraping or updater."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import selectors
import signal
import subprocess
import time
import uuid
from .store import WorkflowError, _atomic_json
from .model_discovery import discovery_key, cached_discovery, store_discovery
from .host_models import delegated_configuration
from .releases import PACKAGE_ROOT
from .process_transport import JsonLineProcess, bounded_capture, stop_tree

MAX_OUTPUT=2*1024*1024


def _cli_version(binary, project):
    try:
        result = run_bounded([binary, '--version'], project, 5)
    except NativeError:
        return None
    match = re.search(r'\d+(?:\.\d+)+', result.stdout) if result.returncode == 0 else None
    return match.group() if match else None

class NativeError(WorkflowError):
    def __init__(self, kind, message='Native invocation failed; inspect host authentication or permissions.'):
        super().__init__('NATIVE_'+kind.upper().replace('-','_'),message)
        self.error_kind=kind


def error_kind(message):
    text=str(message).lower()
    for kind,terms in (('retired',('retired','deprecated model')),('auth',('unauthorized','authentication','not logged in','invalid api key','401')),('quota',('quota','credit balance','insufficient credits','usagelimit')),('rate-limit',('rate limit','rate_limit','ratelimit','429')),('context',('context length','context window','too many tokens','contextwindow','contextlength')),('unavailable',('model not found','model_not_found','not available','unsupported model','not supported','permission denied','403')),('network',('network','connection','timed out','timeout','502','503'))):
        if any(term in text for term in terms):return kind
    return 'unavailable'


def _stop(process):
    if os.name == 'nt':
        try: stop_tree(process)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            raise NativeError('unavailable', 'Native process tree cleanup could not be confirmed.') from exc
        return
    # The group can outlive its leader. Always stop descendants too.
    process.poll()
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    except PermissionError as exc:raise NativeError('unavailable','Native process group cleanup could not be confirmed.') from exc
    try:process.wait(timeout=1)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    except PermissionError as exc:raise NativeError('unavailable','Native process group cleanup could not be confirmed.') from exc
    process.wait(timeout=2)


def run_bounded(argv, cwd, timeout=30):
    """Bound bytes during capture, not after an unbounded communicate()."""
    if os.name == 'nt':
        try: return bounded_capture(argv, cwd, timeout, MAX_OUTPUT)
        except TimeoutError as exc: raise NativeError('network', str(exc)) from exc
        except ValueError as exc: raise NativeError('context', str(exc)) from exc
        except (OSError, RuntimeError) as exc: raise NativeError('unavailable', str(exc)) from exc
    try:process=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    except OSError as exc:raise NativeError('unavailable','Native host executable is unavailable.') from exc
    selector=selectors.DefaultSelector();buffers={}
    for pipe in (process.stdout,process.stderr):selector.register(pipe,selectors.EVENT_READ);buffers[pipe]=bytearray()
    deadline=time.monotonic()+timeout
    try:
        while selector.get_map():
            remaining=deadline-time.monotonic()
            if remaining<=0:raise NativeError('network','Native host timed out; invocation is interrupted.')
            for key,_ in selector.select(min(remaining,1)):
                data=os.read(key.fileobj.fileno(),65536)
                if not data:selector.unregister(key.fileobj);continue
                if len(buffers[key.fileobj])+len(data)>MAX_OUTPUT:raise NativeError('context','Native output exceeds the supported bound.')
                buffers[key.fileobj].extend(data)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise NativeError('network','Native host timed out.')
        process.wait(timeout=remaining)
        return subprocess.CompletedProcess(argv,process.returncode,buffers[process.stdout].decode('utf-8','replace'),buffers[process.stderr].decode('utf-8','replace'))
    finally:
        selector.close()
        try:_stop(process)
        finally:process.stdout.close();process.stderr.close()


class RPC:
    """JSON Lines Codex app-server transport; reject unsupported server requests."""
    def __init__(self,cwd,argv=None):
        self.transport = None
        if os.name == 'nt':
            try: self.transport = JsonLineProcess(argv or ['codex','app-server'], cwd, MAX_OUTPUT)
            except OSError as exc: raise NativeError('unavailable','Codex app-server is unavailable.') from exc
            self.process = self.transport.process
            self.sequence=0;self.notifications=[];self.total=0
            try:
                version=json.loads((PACKAGE_ROOT/'plugin.json').read_text())['version']
                self.request('initialize',{'clientInfo':{'name':'devflow','title':'DevFlow','version':version}})
                self.send({'method':'initialized','params':{}})
            except BaseException:self.close();raise
            return
        try:self.process=subprocess.Popen(argv or ['codex','app-server'],cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
        except OSError as exc:raise NativeError('unavailable','Codex app-server is unavailable.') from exc
        os.set_blocking(self.process.stdin.fileno(),False)
        self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)
        self.buffer=bytearray();self.sequence=0;self.notifications=[];self.total=0
        try:
            version=json.loads((PACKAGE_ROOT/'plugin.json').read_text())['version']
            self.request('initialize',{'clientInfo':{'name':'devflow','title':'DevFlow','version':version}})
            self.send({'method':'initialized','params':{}})
        except BaseException:self.close();raise
    def send(self,value,deadline=None):
        deadline=deadline or time.monotonic()+20
        if self.transport is not None:
            try: self.transport.send(value, max(deadline-time.monotonic(), 0))
            except TimeoutError as exc: raise NativeError('network', str(exc)) from exc
            except ValueError as exc: raise NativeError('context', str(exc)) from exc
            except OSError as exc: raise NativeError('unavailable', str(exc)) from exc
            return
        encoded=(json.dumps(value,separators=(',',':'))+'\n').encode()
        if len(encoded)>MAX_OUTPUT:raise NativeError('context','Native request exceeds supported bound.')
        pending=memoryview(encoded)
        with selectors.DefaultSelector() as writer:
            writer.register(self.process.stdin,selectors.EVENT_WRITE)
            while pending:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise NativeError('network','Codex request write timed out.')
                if not writer.select(min(remaining,1)):continue
                try:count=os.write(self.process.stdin.fileno(),pending[:65536])
                except BlockingIOError:continue
                except OSError as exc:raise NativeError('network','Codex connection closed.') from exc
                pending=pending[count:]
    def next(self,deadline):
        if self.transport is not None:
            try: value=self.transport.next(max(deadline-time.monotonic(), 0))
            except TimeoutError as exc: raise NativeError('network', str(exc)) from exc
            except (ValueError, EOFError) as exc: raise NativeError('unavailable', str(exc)) from exc
            if not isinstance(value,dict):raise NativeError('unavailable','Codex returned unsupported protocol data.')
            if value.get('method') and 'id' in value:
                self.send({'id':value['id'],'error':{'code':-32601,'message':'DevFlow does not authorize this server request.'}},deadline)
            return value
        while b'\n' not in self.buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise NativeError('network','Codex app-server timed out.')
            if not self.selector.select(min(remaining,1)):continue
            data=os.read(self.process.stdout.fileno(),65536)
            if not data:raise NativeError('network','Codex app-server closed before a result.')
            self.total+=len(data)
            if len(self.buffer)+len(data)>MAX_OUTPUT or self.total>32*MAX_OUTPUT:raise NativeError('context','Codex protocol output exceeds the supported bound.')
            self.buffer.extend(data)
        line,_,remaining=self.buffer.partition(b'\n');self.buffer=bytearray(remaining)
        try:value=json.loads(line)
        except (ValueError,UnicodeError) as exc:raise NativeError('unavailable','Codex returned malformed protocol data.') from exc
        if not isinstance(value,dict):raise NativeError('unavailable','Codex returned unsupported protocol data.')
        if value.get('method') and 'id' in value:
            self.send({'id':value['id'],'error':{'code':-32601,'message':'DevFlow does not authorize this server request.'}},deadline)
        return value
    def request(self,method,params,timeout=20):
        self.sequence+=1;identifier=self.sequence;deadline=time.monotonic()+timeout;self.send({'id':identifier,'method':method,'params':params},deadline)
        while True:
            value=self.next(deadline)
            if value.get('id')==identifier and not value.get('method'):
                if value.get('error'):raise NativeError(error_kind(value['error']))
                result=value.get('result')
                if not isinstance(result,dict):raise NativeError('unavailable','Codex response requires an object result.')
                return result
            if value.get('method') and 'id' not in value:
                if len(self.notifications)>=4096:raise NativeError('context','Too many native notifications.')
                self.notifications.append(value)
    def close(self):
        if self.transport is not None:
            try: self.transport.close()
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                raise NativeError('unavailable','Native process cleanup could not be confirmed.') from exc
            return
        self.selector.close()
        try:_stop(self.process)
        finally:self.process.stdin.close();self.process.stdout.close()


class CodexBackend:
    def __init__(self,project,rpc=None):self.project=str(project);self.rpc=rpc or RPC(project);self.configured=None
    def identity(self):
        result=self.rpc.request('account/read',{'refreshToken':False});account=result.get('account')
        if account is None and result.get('requiresOpenaiAuth',True):raise NativeError('auth')
        # APIs without an account identity cannot share discovery across connections.
        stable=isinstance(account,dict) and any(account.get(k) for k in ('email','id','accountId'))
        stamp=account if stable else {'account':account,'connection':uuid.uuid4().hex}
        return {'account_key':hashlib.sha256(json.dumps(stamp,sort_keys=True).encode()).hexdigest(),'cacheable':stable}
    def discover(self):
        models={};efforts={};revisions={};cursor=None;seen=set()
        for _ in range(32):
            params={'limit':100,'includeHidden':False}
            if cursor:params['cursor']=cursor
            result=self.rpc.request('model/list',params)
            for entry in result.get('data',[]):
                model=entry.get('model')
                if isinstance(model,str) and model:
                    models[model]='available';efforts[model]=[e['reasoningEffort'] for e in entry.get('supportedReasoningEfforts',[]) if isinstance(e,dict) and isinstance(e.get('reasoningEffort'),str)]
                    if isinstance(entry.get('revision'),str) and entry['revision']:
                        revisions[model]=entry['revision']
            cursor=result.get('nextCursor')
            if not cursor:break
            if cursor in seen:raise NativeError('unavailable','Native model pagination is inconsistent.')
            seen.add(cursor)
        else:raise NativeError('context','Native model inventory exceeds supported pages.')
        return {'capabilities':{'configure':True,'observe':True,'models':list(models),'efforts':sorted({e for values in efforts.values() for e in values}),'model_efforts':efforts},'discovery':{'models':models,'model_revisions':revisions,'host_version':_cli_version('codex',self.project),'source':'codex-app-server-model-list'}}
    def configure(self,resolved,brief,access='read-only'):
        settings=self.rpc.request('config/read',{'includeLayers':False,'cwd':self.project}).get('config',{})
        servers=settings.get('mcp_servers',{}) if isinstance(settings,dict) else {}
        overrides={'model_reasoning_effort':resolved['effort'],'features':{'apps':False}}
        if isinstance(servers,dict):overrides['mcp_servers']={name:{'enabled':False} for name in servers}
        result=self.rpc.request('thread/start',{'model':resolved['model'],'config':overrides,'cwd':self.project,'ephemeral':True,'approvalPolicy':'never','sandbox':'workspace-write' if access=='workspace-write' else 'read-only','developerInstructions':brief,'serviceName':'devflow'})
        thread=result.get('thread',{});identifier=thread.get('id')
        if not isinstance(identifier,str) or not identifier:raise NativeError('unavailable','Codex did not return a native thread identity.')
        self.configured={'observed':{'provider':result.get('modelProvider'),'model':result.get('model'),'effort':result.get('reasoningEffort')},'observation_source':'host-effective-configuration','invocation_ref':'codex://'+identifier,'native_session_id':thread.get('sessionId'),'thread_id':identifier}
        return self.configured
    def invoke(self,resolved,prompt,actor,access='read-only',timeout=300):
        if not self.configured:self.configure(resolved,'DevFlow actor '+actor,access)
        thread=self.configured['thread_id'];self.rpc.request('turn/start',{'threadId':thread,'input':[{'type':'text','text':prompt}]})
        deadline=time.monotonic()+timeout;messages=[];usage=None;rerouted=False
        while True:
            value=self.rpc.notifications.pop(0) if self.rpc.notifications else self.rpc.next(deadline)
            params=value.get('params',{})
            if params.get('threadId') not in {None,thread}:continue
            if value.get('method')=='model/rerouted':
                rerouted=True;self.configured['observed']={**self.configured['observed'],'model':params.get('toModel')}
            if value.get('method')=='item/completed':
                item=params.get('item',{})
                if item.get('type')=='agentMessage' and isinstance(item.get('text'),str):messages.append(item['text'])
            if value.get('method')=='thread/tokenUsage/updated':usage=params.get('tokenUsage')
            if value.get('method')=='turn/completed':
                turn=params.get('turn',{})
                if turn.get('status')!='completed':raise NativeError(error_kind(turn.get('error') or 'unavailable'))
                return {**self.configured,'status':'interrupted' if rerouted else 'completed','error_kind':'unavailable' if rerouted else None,'reason_code':'MODEL_SUBSTITUTED' if rerouted else 'NATIVE_INVOCATION_COMPLETED','output':'\n'.join(messages),'usage':usage}
    def close(self):self.rpc.close()


class ClaudeBackend:
    def __init__(self,project):self.project=str(project)
    def identity(self):
        result=run_bounded(['claude','auth','status','--json'],self.project,15)
        if result.returncode:raise NativeError('auth')
        try:account=json.loads(result.stdout)
        except ValueError as exc:raise NativeError('auth','Claude auth status is unavailable.') from exc
        if not isinstance(account,dict) or account.get('loggedIn') is not True:raise NativeError('auth')
        if account.get('apiProvider') not in {None,'firstParty','anthropic'}:raise NativeError('unavailable','This adapter requires first-party Claude authentication; other provider identity is unsupported.')
        stable=any(account.get(k) for k in ('email','accountId','orgId'))
        stamp=account if stable else {'authMethod':account.get('authMethod'),'connection':uuid.uuid4().hex}
        return {'account_key':hashlib.sha256(json.dumps(stamp,sort_keys=True).encode()).hexdigest(),'cacheable':stable}
    def discover(self):
        result=run_bounded(['claude','--help'],self.project,15)
        supported=result.returncode==0 and all(flag in result.stdout for flag in ('--agents','--agent','--model','--effort','--tools','--output-format','--strict-mcp-config'))
        return {'capabilities':{'configure':supported,'observe':False,'models':[],'efforts':['low','medium','high','xhigh','max'] if supported else [],'model_efforts':{}},'discovery':{'models':{},'model_revisions':{},'host_version':_cli_version('claude',self.project),'source':'selected-model-native-launch-required'}}
    def invoke(self,resolved,prompt,actor,access='read-only',timeout=300):
        name='devflow-'+hashlib.sha256(actor.encode()).hexdigest()[:16]
        rendered=delegated_configuration({'status':'allow','resolved':resolved},'claude',name)
        agents=rendered['agents'];agents[name]['prompt']='You are the scoped DevFlow actor '+actor+'. Preserve work identity. '+agents[name]['prompt']
        tools='' if access=='none' else 'Read,Glob,Grep' if access=='read-only' else 'Read,Glob,Grep,Edit,Write,Bash'
        argv=['claude','-p',prompt,'--agents',json.dumps(agents,separators=(',',':')),'--agent',name,'--model',resolved['model'],'--effort',resolved['effort'],'--output-format','json','--tools',tools,'--permission-mode','dontAsk','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--disable-slash-commands']
        if access=='workspace-write':argv.extend(['--allowedTools','Edit(./**),Write(./**)'])
        result=run_bounded(argv,self.project,timeout)
        if result.returncode:raise NativeError(error_kind(result.stderr+' '+result.stdout))
        try:payload=json.loads(result.stdout)
        except ValueError as exc:raise NativeError('unavailable','Claude returned malformed native output.') from exc
        if not isinstance(payload,dict) or payload.get('is_error'):raise NativeError(error_kind(payload.get('result','unavailable') if isinstance(payload,dict) else 'unavailable'))
        models=list(payload.get('modelUsage',{}));model=models[0] if len(models)==1 else None
        return {'status':'completed','observed':{'provider':'anthropic','model':model,'effort':None},'observation_source':'host-invocation-metadata','invocation_ref':'claude://'+str(payload.get('session_id','')),'native_session_id':payload.get('session_id'),'output':payload.get('result',''),'usage':payload.get('usage')}
    def close(self):pass


class NativeCache:
    def __init__(self,root):self.path=Path(root)/'native-model-discovery.json'
    def read(self):
        try:value=json.loads(self.path.read_text());return value if isinstance(value,dict) else {}
        except (OSError,ValueError):return {}
    def key(self,host,account,policy,release):return discovery_key(host,account,policy+':'+release)
    def put(self,host,account,policy,release,result,now,ttl=900):
        cache={k:v for k,v in self.read().items() if isinstance(v,dict) and isinstance(v.get('expires_at'),(int,float)) and v['expires_at']>now}
        store_discovery(cache,self.key(host,account,policy,release),result,now,ttl)
        if len(cache)>128:cache=dict(sorted(cache.items(),key=lambda item:item[1].get('recorded_at',0),reverse=True)[:128])
        self.path.parent.mkdir(parents=True,exist_ok=True);_atomic_json(self.path,cache)
    def get(self,host,account,policy,release,now):
        try:return cached_discovery(self.read(),self.key(host,account,policy,release),now)
        except (KeyError,TypeError,ValueError):return None
    def invalidate(self,host,account,policy,release):
        cache=self.read();cache.pop(self.key(host,account,policy,release),None);self.path.parent.mkdir(parents=True,exist_ok=True);_atomic_json(self.path,cache)
