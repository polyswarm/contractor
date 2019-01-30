import io
import os

from contractor.util import call_with_output


def test_call_with_output():
    out = io.BytesIO()
    assert call_with_output(['echo', 'foo'], file=out) == 0
    assert out.getvalue() == b'foo' + os.linesep.encode('utf-8')
