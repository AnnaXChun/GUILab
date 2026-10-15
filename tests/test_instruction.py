import pytest
from cad_cf.instruction import normalize_instruction

@pytest.mark.parametrize('prefix', ['Use GUI, ', 'Use GUI. ', 'Use GUI,'])
def test_only_exact_prefix(prefix):
    assert normalize_instruction(prefix+'Create Pad Length 12 mm at /home/user/Unnamed.FCStd.') == 'Create Pad Length 12 mm at /home/user/Unnamed.FCStd.'

@pytest.mark.parametrize('raw', ['Use GUI to create Pad', 'Do not Use GUI, change 7 mm', 'use GUI, Keep dimensions', 'Use GUI: Test'])
def test_other_text_unchanged(raw):
    assert normalize_instruction(raw) == raw
