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
            offset=1 if func.attr in SCROLL else 0
            pairs.update({axis:('arg',i) for i,axis in enumerate(('x','y'),start=offset) if len(node.args)>i})
            for keyword in node.keywords:
                if keyword.arg in ('x','y'):
                    if keyword.arg in pairs:raise ValueError('duplicate absolute coordinate argument')
                    pairs[keyword.arg]=('kw',keyword)
            if not pairs:return node
            if set(pairs)!= {'x','y'}:raise ValueError('normalized GUI action requires both x and y')
            for axis,(kind,target) in pairs.items():
                old=node.args[target] if kind=='arg' else target.value
                # Handle negative literals: ast.UnaryOp(USub, Constant(5)) -> -5
                if isinstance(old, ast.UnaryOp) and isinstance(old.op, ast.USub) and isinstance(old.operand, ast.Constant):
                    v = -old.operand.value
                elif isinstance(old, ast.Constant) and type(old.value) in (int, float) and math.isfinite(old.value):
                    v = old.value
                else:
                    raise ValueError('unparseable literal coordinate')
                # Clamp: models occasionally emit values slightly outside 0..1000.
                # A hard rejection kills the episode; clamping preserves the intent.
                clamped = max(0, min(1000, v))
                bound=width if axis=='x' else height
                new_pixel = min(bound - 1, int(round(clamped * bound / 1000)))
                new = ast.copy_location(ast.Constant(new_pixel), old)
                if kind == 'arg':
                    node.args[target] = new
                else:
                    target.value = new
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
              'Relative mouse movement and scroll amounts remain unchanged. '
              'Recent trajectory actions use this same normalized coordinate system; converted pixel positions are retained only in execution logs.')
    def adapt_actions(self,agent,actions,obs):
        raw=self.delegate.adapt_actions(agent,actions,obs)
        width,height=agent._screenshot_size(obs)
        scaled=[scale_action(action,width,height) for action in raw]
        self.last_normalized_actions=list(raw)
        agent._log_info('Qwen coordinate mapping normalized1000 -> pixels %sx%s: %s -> %s',width,height,raw,scaled)
        return scaled


class OriginalPromptNormalizedQwenAdapter(NormalizedQwenAdapter):
    """Explicit service-unit experiment; preserve the pinned pixel prompt."""
    name='Qwen3-6-normalized1000-original-prompt'

    def prompt_suffix(self,agent):
        return self.delegate.prompt_suffix(agent)


def install_qwen_coordinates(*, preserve_pixel_prompt=False):
    from baseline import provider_adapter
    from scripts.python.api_agent import CADWorldAPIModelAgent
    original=provider_adapter.load_from_env
    original_remember=CADWorldAPIModelAgent._remember_turn
    def load(model=None,provider=None):
        delegate=original(model=model,provider=provider)
        if not model or 'qwen3' not in model.lower() or delegate.name!='Qwen3-6':
            raise ValueError('normalized1000 requires the pinned Qwen3-6 adapter and a Qwen3 model')
        adapter=OriginalPromptNormalizedQwenAdapter if preserve_pixel_prompt else NormalizedQwenAdapter
        return adapter(delegate)
    def remember(agent,obs,response,actions):
        adapter=agent.provider_adapter
        if isinstance(adapter,NormalizedQwenAdapter):
            normalized=list(adapter.last_normalized_actions)
            # The upstream prompt serializes both model_action and executed_action.
            # Keep their online units consistent; actual pixel execution remains
            # unchanged in the returned response and complete episode JSONL.
            response['coordinate_mapping']={'protocol_version':3 if preserve_pixel_prompt else 2,'model_unit':'normalized1000',
                'prompt_protocol':'original_pixels' if preserve_pixel_prompt else 'explicit_normalized1000',
                'history_unit':'normalized1000','model_actions':normalized,'executed_pixel_actions':list(actions)}
            return original_remember(agent,obs,response,normalized)
        return original_remember(agent,obs,response,actions)
    provider_adapter.load_from_env=load
    CADWorldAPIModelAgent._remember_turn=remember
    def restore():
        provider_adapter.load_from_env=original
        CADWorldAPIModelAgent._remember_turn=original_remember
    return restore
