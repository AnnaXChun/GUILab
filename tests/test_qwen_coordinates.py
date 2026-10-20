import pytest
from cad_cf.qwen_coordinates import scale_action


@pytest.mark.parametrize('source,expected',[
    ('pyautogui.click(x=841,y=740)','pyautogui.click(x=1615, y=799)'),
    ('pyautogui.moveTo(500,500,duration=0.3)','pyautogui.moveTo(960, 540, duration=0.3)'),
    ('pyautogui.scroll(-3,x=500,y=500)','pyautogui.scroll(-3, x=960, y=540)'),
    ('pyautogui.scroll(-3,500,500)','pyautogui.scroll(-3, 960, 540)'),
    ('pyautogui.moveRel(100,10)','pyautogui.moveRel(100, 10)'),
    ('pyautogui.click(x=1000,y=1000)','pyautogui.click(x=1919, y=1079)'),
    ('pyautogui.hotkey("ctrl","s")',"pyautogui.hotkey('ctrl', 's')"),
    ('DONE','DONE'),
])
def test_coordinate_units_and_non_coordinate_values(source,expected):
    assert scale_action(source,1920,1080)==expected


@pytest.mark.parametrize('source',['pyautogui.click(x=1200,y=500)','pyautogui.click(x=target,y=500)','pyautogui.click(x=50)','pyautogui.click(500,500,x=500)'])
def test_ambiguous_or_out_of_range_coordinates_are_not_executed(source):
    with pytest.raises(ValueError):scale_action(source,1920,1080)


@pytest.mark.parametrize('preserve_pixel_prompt', [False, True])
def test_real_upstream_multiturn_history_does_not_feed_pixel_actions_back(monkeypatch,preserve_pixel_prompt):
    import io
    from pathlib import Path
    image=pytest.importorskip('PIL.Image')
    upstream=Path(__file__).resolve().parents[1]/'vendor/CADWORLD'
    monkeypatch.syspath_prepend(str(upstream))
    monkeypatch.setenv('CADWORLD_BASELINE_PROVIDER','Qwen3-6')
    from scripts.python.api_agent import CADWorldAPIModelAgent
    from cad_cf.qwen_coordinates import install_qwen_coordinates
    original_remember=CADWorldAPIModelAgent._remember_turn
    stream=io.BytesIO();image.new('RGB',(1920,1080),'white').save(stream,format='PNG')
    obs={'screenshot':stream.getvalue()}
    restore=install_qwen_coordinates(preserve_pixel_prompt=preserve_pixel_prompt)
    try:
        agent=CADWorldAPIModelAgent(provider='openai-compatible',model='qwen3.6-35b-a3b',think_level='none')
        agent.reset(max_steps=3)
        raw='pyautogui.click(x=805, y=283)'
        prompts=[]
        def query(instruction,observation):
            prompts.append(agent._prompt(instruction,observation))
            return {'status':'ok','action':raw,'actions':[raw],'raw_response':'{"action":"'+raw+'"}'}
        monkeypatch.setattr(agent,'_query_model',query)
        for _ in range(2):
            response,actions=agent.predict('Inspect the public empty GUI.',obs)
            assert actions==['pyautogui.click(x=1546, y=306)']
            assert response['executed_action']==actions[0]
            assert response['coordinate_mapping']['executed_pixel_actions']==actions
        assert raw in prompts[1]
        assert 'pyautogui.click(x=1546, y=306)' not in prompts[1]
        assert agent.trajectory[-1]['executed_action']==raw
        if preserve_pixel_prompt:
            assert agent.provider_adapter.prompt_suffix(agent)==agent.provider_adapter.delegate.prompt_suffix(agent)
            assert 'using pixel coordinates on the original screenshot' in prompts[1]
            assert 'normalized coordinate system' not in prompts[1]
            assert response['coordinate_mapping']['protocol_version']==3
        else:
            assert 'normalized coordinate system' in prompts[1]
    finally:restore()
    assert CADWorldAPIModelAgent._remember_turn is original_remember
