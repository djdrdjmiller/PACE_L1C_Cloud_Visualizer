"""Download and verify the explicit derived-data release artifact for Pages."""
import hashlib,json,stat,subprocess,zipfile
from pathlib import Path,PurePosixPath
m=json.loads(Path('.github/showcase-manifest.json').read_text())
subprocess.run(['gh','release','download',m['tag'],'--pattern',m['asset'],'--dir','.showcase-download'],check=True)
p=Path('.showcase-download')/m['asset']
if p.stat().st_size!=m['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=m['sha256']:
    raise ValueError('Showcase artifact identity mismatch')
with zipfile.ZipFile(p) as z:
    for info in z.infolist():
        path=PurePosixPath(info.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in info.filename or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe archive entry')
        if path.suffix.lower() in ('.nc','.nc4','.hdf','.h5','.ipynb'):raise ValueError('Raw science/reference file in showcase')
    if sum(i.file_size for i in z.infolist())>100_000_000:raise ValueError('Showcase exceeds static size limit')
    z.extractall('_site')
assert Path('_site/index.html').is_file()
