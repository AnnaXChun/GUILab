"""Explicit Qwen 0..1000 absolute coordinates, converted once to GUI pixels."""
import ast
import math

ABSOLUTE={'click','rightClick','doubleClick','tripleClick','moveTo','dragTo','mouseDown','mouseUp'}
SCROLL={'scroll','hscroll','vscroll'}


def scale_action(source,width,height):
    if source in ('WAIT','DONE','FAIL'):return source
    if width<1 or height<1:raise ValueError('positive screenshot dimensions required')
    class Coordinates(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            func=node.func
            if not (isinstance(func,ast.Attribute) and isinstance(func.value,ast.Name) and func.value.id=='pyautogui'):
                return node
            if func.attr not in ABSOLUTE|SCROLL:return node
            pairs={}
            if func.attr in ABSOLUTE:
                pairs.update({axis:('arg',i) for i,axis in enumerate(('x','y')) if len(node.args)>i})
            for keyword in node.keywords:
                if keyword.arg in ('x','y'):pairs[keyword.arg]=('kw',keyword)
            if not pairs:return node
            if set(pairs)!= {'x','y'}:raise ValueError('normalized GUI action requires both x and y')
            for axis,(kind,target) in pairs.items():
                old=node.args[target] if kind=='arg' else target.value
                if not isinstance(old,ast.Constant) or type(old.value) not in (int,float) or not math.isfinite(old.value) or not 0<=old.value<=1000:
                    raise ValueError('literal Qwen coordinates must be in 0..1000')
                bound=width if axis=='x' else height
                new=ast.copy_location(ast.Constant(min(bound-1,int(round(old.value*bound/1000)))),old)
                if kind=='arg':node.args[target]=new
                else:target.value=new
            return node
    tree=Coordinates().visit(ast.parse(source));ast.fix_missing_locations(tree)
    return ast.unparse(tree)


class NormalizedQwenAdapter:
    name='Qwen3-6-normalized1000'
    def __init__(self,delegate):self.delegate=delegate
    def __getattr__(self,name):return getattr(self.delegate,name)
    def prompt_suffix(self,agent):
        original=self.delegate.prompt_suffix(agent)
        return original.replace('pyautogui actions using pixel coordinates on the original screenshot.',
            'For every absolute mouse position, emit x and y as normalized coordinates in 0..1000, independently for each axis. '
            'The execution adapter converts these normalized positions to the original screenshot pixels. '
            'Relative mouse movement and scroll amounts remain unchanged.')
    def adapt_actions(self,agent,actions,obs):
        raw=self.delegate.adapt_actions(agent,actions,obs)
        width,height=agent._screenshot_size(obs)
        scaled=[scale_action(action,width,height) for action in raw]
        agent._log_info('Qwen coordinate mapping normalized1000 -> pixels %sx%s: %s -> %s',width,height,raw,scaled)
        return scaled


def install_qwen_coordinates():
    from baseline import provider_adapter
    original=provider_adapter.load_from_env
    def load(model=None,provider=None):
        delegate=original(model=model,provider=provider)
        if not model or 'qwen3' not in model.lower() or delegate.name!='Qwen3-6':
            raise ValueError('normalized1000 requires the pinned Qwen3-6 adapter and a Qwen3 model')
        return NormalizedQwenAdapter(delegate)
    provider_adapter.load_from_env=load
    return lambda:setattr(provider_adapter,'load_from_env',original)
