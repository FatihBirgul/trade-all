"""Native release audit: compare actual APK font bytes; no device-test claim."""
import hashlib
import sys
import zipfile
from pathlib import Path

font = Path('node_modules/@expo/vector-icons/build/vendor/react-native-vector-icons/Fonts/Ionicons.ttf').read_bytes()
digest = hashlib.sha256(font).hexdigest()
with zipfile.ZipFile(sys.argv[1]) as apk:
    assert apk.testzip() is None, 'APK ZIP CRC failed'
    assert any(n.endswith('index.android.bundle') for n in apk.namelist()), 'Missing embedded JS'
    matches = [n for n in apk.namelist() if n.endswith('.ttf') and hashlib.sha256(apk.read(n)).hexdigest() == digest]
    assert len(matches) == 1, 'Ionicons font bytes missing or ambiguous in native APK'
    print('PASS: native Ionicons font SHA-256', digest, 'asset', matches[0], '; embedded JS and ZIP CRC')
