import py_compile
import sys
try:
    py_compile.compile('../app.py', doraise=True)
    print('OK')
except Exception as e:
    print('ERR', e)
    sys.exit(1)
