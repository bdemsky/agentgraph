from typing import Any, Optional, Union
from pathlib import Path

from agentgraph.core.mutable import Mutable

class ReadFileStore:
    def __init__(self, store: 'FileStore'):
        self.filestore = store.filestore.copy()
    
    def __contains__(self, key: str) -> bool:
        return key in self.filestore

    def __getitem__(self, key: str) -> str:
        return self.filestore[key]

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        files = self.get_files()
        return files.__iter__()

    def get_files(self):
        return list(self.filestore)
        
        
class FileStore(Mutable):
    def __init__(self):
        super().__init__()
        self.filestore = dict()

    def _snapshot(self):
        return ReadFileStore(self)
        
    def __contains__(self, key: str) -> bool:
        self.waitForAccess()
        return key in self.filestore

    def __getitem__(self, key: str) -> str:
        self.waitForAccess()
        return self.filestore[key]

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        self.waitForAccess()
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: Union[str, Path], val: str) -> None:
        self.waitForAccess()
        if str(key).startswith("../"):
            raise ValueError(f"File name {key} attempted to access parent path.")

        assert isinstance(val, str), "val must be str"
        self.filestore[key] = val

    def __iter__(self):
        self.waitForAccess()
        files = self.get_files()
        return files.__iter__()

    def get_files(self):
        self.waitForAccess()
        return list(self.filestore)

    def __delitem__(self, key: Union[str, Path]) -> None:
        self.waitForAccess()
        del self.filestore[key]

    def writeFiles(self, path: Union[str, Path]):
        """Write all files to path."""

        self.waitForAccess()
        filepath: Path = Path(path).absolute()
        filepath.mkdir(parents=True, exist_ok=True)
        for key in self.filestore:
            contents = self.filestore[key]
            full_path = filepath / key
            full_path.parent.mkdir(parents = True, exist_ok = True)
            full_path.write_text(contents, encoding="utf-8")
            
